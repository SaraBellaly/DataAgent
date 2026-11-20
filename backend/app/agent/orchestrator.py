"""
Boucle de l'agent : question -> appels d'outils en lecture seule -> réponse (SQL proposé non exécuté).

1. Contexte : instructions + échanges récents de CET utilisateur seulement (table historique).
2. Le modèle appelle des outils ; l'application les exécute (analyst_ro) et lui renvoie le résultat.
3. L'outil repondre clôt la boucle. Le SQL proposé est vérifié (une seule instruction SELECT
   autorisée) puis testé par EXPLAIN, sans exécution. En cas d'erreur, elle est renvoyée au modèle
   pour qu'il corrige.
4. L'échange n'est enregistré qu'en cas de succès. En cas d'échec, rien n'est inventé ni enregistré.
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app import repositories as repo
from app.agent import tools
from app.agent.llm import ChatClient
from app.agent.prompts import SYSTEM_PROMPT, TOOLS
from app.agent.sql_guard import SqlRejected
from app.core.config import settings
from app.db.connection import pool_app

logger = logging.getLogger(__name__)


class AgentFailed(Exception):
    """L'agent n'a pas produit de réponse exploitable (message présentable à l'utilisateur)."""


@dataclass
class AgentAnswer:
    history_id: int
    question: str
    sql_propose: str | None
    explication: str
    recommandations: list[str]
    etapes: list[str] = field(default_factory=list)
    tokens: int | None = None
    diagnostic_performance: str | None = None   # fiche, 5.1 : diagnostic si la requête est lente
    duree_modele_ms: float = 0.0                # fiche, Q13 : temps du modèle…
    duree_base_ms: float = 0.0                  # … séparé de celui de la base (outils, EXPLAIN)
    conversation_id: int | None = None
    modele: str | None = None          # modèle qui a produit la réponse finale
    modele_secours: bool = False       # True si le modèle principal était épuisé


@dataclass
class _Run:
    """État d'une question en cours : étapes, tokens et temps mesurés."""
    steps: list[str] = field(default_factory=list)
    tokens: int = 0
    llm_ms: float = 0.0
    db_ms: float = 0.0
    conversation_id: int | None = None
    model: str | None = None
    fallback: bool = False

    def timed_db(self, fn: Callable[[], Any]) -> Any:
        start = time.perf_counter()
        try:
            return fn()
        finally:
            self.db_ms += (time.perf_counter() - start) * 1000


def _truncate(text: str) -> str:
    limit = settings.agent_max_tool_chars
    return text if len(text) <= limit else text[:limit] + f"\n[… tronqué à {limit} caractères]"


def _as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


# Outils consultatifs : leur résultat est renvoyé au modèle
_TOOL_HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "lire_schema": lambda args: tools.read_schema(),
    "chercher_commune": lambda args: _as_json(tools.find_commune(str(args.get("nom", "")))),
    "requetes_couteuses": lambda args: _as_json(
        tools.costly_queries(int(args.get("limite") or 10), str(args.get("tri") or "total"))),
    "expliquer_requete": lambda args: tools.explain_select(str(args.get("sql", ""))),
}


def _history_context(user_id: int, conversation_id: int | None) -> list[dict[str, Any]]:
    """Échanges récents de la conversation en cours (de CET utilisateur), du plus ancien au plus récent.
    Une nouvelle conversation part sans contexte.

    Chaque réponse passée est rejouée sous sa forme réelle, un appel à l'outil repondre :
    présentée en texte libre, elle incitait le modèle à répondre lui aussi en texte, sans
    outil (refusé par Groq : tool_use_failed, constaté sur « et à Toulouse ? »)."""
    if conversation_id is None:
        return []
    with pool_app.connection() as conn:
        items = repo.conversation_history(conn, user_id, conversation_id, last=settings.agent_history_turns)
    messages: list[dict[str, Any]] = []
    for item in items:
        call_id = f"historique_{item['id']}"
        args = {"explication": (item["explication"] or "")[:500]}
        if item["sql_propose"]:
            args["sql_propose"] = item["sql_propose"][:800]
        messages.append({"role": "user", "content": item["question"]})
        messages.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": "repondre", "arguments": _as_json(args)}}]})
        messages.append({"role": "tool", "tool_call_id": call_id, "content": "Réponse transmise à l'utilisateur."})
    return messages


_SQL_BLOCK = re.compile(r"```\s*(?:sql|postgresql|postgres)?\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)


def _split_sql_block(text: str) -> tuple[str | None, str]:
    """Sépare le premier bloc ```sql d'une réponse en texte ; renvoie (sql, texte sans le bloc).
    Plusieurs blocs : seul le premier est proposé (une seule instruction par réponse)."""
    match = _SQL_BLOCK.search(text or "")
    if not match:
        return None, (text or "").strip()
    sql = match.group(1).strip()
    rest = (text[:match.start()] + text[match.end():]).strip()
    # Titres Markdown que gpt-oss ajoute (« **SQL proposé** : », « **Explication** »)
    rest = re.sub(r"\*\*\s*(SQL propos[ée]|Explication)\s*\*\*\s*:?", "", rest, flags=re.IGNORECASE).strip()
    return (sql or None), rest


def _json_answer(text: str) -> dict[str, Any] | None:
    """Réponse du modèle qui n'est qu'un objet JSON (éventuellement dans un bloc ```json)
    contenant au moins « explication » : on la lit comme les arguments de repondre."""
    candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.IGNORECASE)
    if not (candidate.startswith("{") and candidate.endswith("}")):
        return None
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) and "explication" in data else None


def _validate_final_sql(sql: str | None, run: _Run) -> tuple[str | None, str | None]:
    """Vérifie le SQL final et renvoie (sql, diagnostic de performance).
    Lève SqlRejected / ToolError, dont le message est renvoyé au modèle pour correction."""
    if not sql or not sql.strip():
        return None, None
    checked = tools.check(sql)                                   # un seul SELECT autorisé
    plan = run.timed_db(lambda: tools.explain_select(checked.sql))  # colonne inventée… (sans exécuter)
    return checked.sql, tools.performance_diagnosis(checked.sql, plan)


def ask(user_id: int, question: str, llm: ChatClient, conversation_id: int | None = None) -> AgentAnswer:
    """conversation_id : conversation à poursuivre (son appartenance à l'utilisateur est vérifiée
    par l'appelant) ; None crée une conversation, intitulée d'après la question, au premier succès."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += _history_context(user_id, conversation_id)
    messages.append({"role": "user", "content": question})

    run = _Run(conversation_id=conversation_id)
    reminded = False
    for _ in range(settings.agent_max_steps):
        start = time.perf_counter()
        try:
            reply = llm.complete(messages, TOOLS)    # LLMUnavailable remonte tel quel
        finally:
            run.llm_ms += (time.perf_counter() - start) * 1000
        run.tokens += reply.get("usage") or 0
        run.model = reply.get("model") or run.model
        run.fallback = run.fallback or bool(reply.get("fallback"))
        calls = reply.get("tool_calls") or []

        if not calls:
            text = (reply.get("content") or "").strip()
            # Arguments de repondre écrits en JSON dans le texte (vu avec gpt-oss) : traités comme
            # un vrai appel, avec les mêmes vérifications
            json_args = _json_answer(text)
            if json_args is not None:
                calls = [{"id": "texte_json", "name": "repondre", "arguments": _as_json(json_args)}]
                run.steps.append("texte_json")
        if not calls:
            # Réponse rédigée en texte (Markdown) au lieu d'un appel à repondre : le SQL éventuel
            # (bloc ```sql) passe par les MÊMES vérifications qu'un appel à repondre.
            sql_text, explanation = _split_sql_block(text)
            if sql_text:
                try:
                    sql, diagnosis = _validate_final_sql(sql_text, run)
                except (SqlRejected, tools.ToolError) as e:
                    run.steps.append("sql_refuse")
                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user", "content":
                                     f"Requête refusée : {e} Corrige-la et appelle l'outil repondre."})
                    continue
                run.steps.append("texte")
                return _save(user_id, question, sql, explanation or "(sans explication)", [], diagnosis, run)
            if not text and not reminded:
                reminded = True
                run.steps.append("rappel")
                messages.append({"role": "user", "content": "Réponds en appelant l'outil repondre."})
                continue
            if not text:
                raise AgentFailed("L'agent n'a renvoyé aucune réponse. Reformulez la question.")
            run.steps.append("texte")
            return _save(user_id, question, None, text, [], None, run)

        messages.append({
            "role": "assistant",
            "content": reply.get("content") or "",
            "tool_calls": [{"id": c["id"], "type": "function",
                            "function": {"name": c["name"], "arguments": c["arguments"]}} for c in calls],
        })

        for call in calls:
            name = call["name"]
            run.steps.append(name)
            try:
                args = json.loads(call["arguments"] or "{}")
                if not isinstance(args, dict):
                    raise ValueError("arguments non conformes")
            except (json.JSONDecodeError, ValueError):
                messages.append(_tool_message(call, "ERREUR : arguments JSON invalides."))
                continue

            if name == "repondre":
                try:
                    sql, diagnosis = _validate_final_sql(args.get("sql_propose"), run)
                except (SqlRejected, tools.ToolError) as e:
                    run.steps.append("sql_refuse")
                    messages.append(_tool_message(
                        call, f"ERREUR : requête refusée, corrige-la puis rappelle repondre. {e}"))
                    continue
                explanation = str(args.get("explication") or "").strip() or "(sans explication)"
                recos = [str(r) for r in (args.get("recommandations") or []) if str(r).strip()][:10]
                return _save(user_id, question, sql, explanation, recos, diagnosis, run)

            handler = _TOOL_HANDLERS.get(name)
            if handler is None:
                messages.append(_tool_message(call, f"ERREUR : outil inconnu {name}."))
                continue
            try:
                result = run.timed_db(lambda: handler(args))
            except (SqlRejected, tools.ToolError) as e:
                result = f"ERREUR : {e}"
            messages.append(_tool_message(call, _truncate(result)))

    raise AgentFailed("L'agent n'a pas abouti dans le nombre d'étapes autorisé. Reformulez ou précisez la question.")


def _tool_message(call: dict[str, Any], content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call["id"], "content": content}


def _save(user_id: int, question: str, sql: str | None, explanation: str,
          recos: list[str], diagnosis: str | None, run: _Run) -> AgentAnswer:
    with pool_app.connection() as conn:
        # Conversation créée seulement en cas de succès : un échec n'enregistre rien (fiche, Q10)
        if run.conversation_id is None:
            run.conversation_id = repo.create_conversation(conn, user_id, question)
        history_id = repo.add_history(conn, user_id, question, sql, explanation, recos, run.conversation_id)
        repo.touch_conversation(conn, user_id, run.conversation_id)
    logger.info("Question traitée par %s%s : %d étapes, %s tokens, modèle %.0f ms, base %.0f ms, SQL=%s",
                run.model or "?", " (secours)" if run.fallback else "", len(run.steps), run.tokens or "?",
                run.llm_ms, run.db_ms, bool(sql))
    return AgentAnswer(history_id, question, sql, explanation, recos, run.steps, run.tokens or None,
                       diagnosis, round(run.llm_ms, 1), round(run.db_ms, 1), run.conversation_id,
                       run.model, run.fallback)
