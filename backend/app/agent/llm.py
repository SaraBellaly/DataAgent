"""
Client du modèle de langage : toute API compatible OpenAI (chat completions + appel d'outils).

Fournisseur choisi dans .env, sans changer le code :
  Groq   : LLM_BASE_URL=https://api.groq.com/openai/v1   LLM_MODEL=openai/gpt-oss-120b
  Ollama : LLM_BASE_URL=http://localhost:11434/v1        LLM_MODEL=qwen3:8b   (clé vide)

Toute erreur du fournisseur devient LLMUnavailable : l'application affiche un message clair,
n'invente aucune réponse et n'enregistre rien dans l'historique (fiche, Q10).
"""
import logging
import math
import time
from typing import Any, Protocol

import openai

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ChatClient(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Renvoie le message de l'assistant : {"content": str | None, "tool_calls": [...]}"""


class _RateLimited(Exception):
    def __init__(self, seconds: int | None):
        self.seconds = seconds


# Au-delà de ce délai, mieux vaut passer au modèle suivant que d'attendre…
SHORT_WAIT_SECONDS = 20
# … sauf s'il n'y a plus de modèle de secours : on patiente alors jusqu'à une minute avant de renoncer
LAST_RESORT_WAIT_SECONDS = 60


class OpenAICompatibleClient:
    """Chaîne de modèles : principal (LLM_MODEL), puis secours (LLM_FALLBACK_MODELS) quand le quota
    du principal est épuisé. Une courte limite par minute est attendue sur le même modèle ; un quota
    épuisé pour longtemps fait passer au suivant, et le modèle épuisé est mis de côté jusqu'à son
    rétablissement (pas d'appel inutile à chaque étape)."""

    def __init__(self) -> None:
        self._client = openai.OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value() or "sans-cle",  # Ollama n'en demande pas
            timeout=settings.llm_timeout_seconds,
            max_retries=0,   # les limites de débit sont gérées ici (attente courte ou bascule)
        )
        self.models = [settings.llm_model, *[m for m in settings.llm_fallback_models if m != settings.llm_model]]
        self._exhausted_until: dict[str, float] = {}

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        now = time.monotonic()
        available = [m for m in self.models if self._exhausted_until.get(m, 0) <= now]
        if not available:
            wait = max(1, math.ceil(min(self._exhausted_until.values()) - now))
            raise LLMUnavailable(f"Le service d'analyse est momentanément saturé : réessayez dans {wait} s.", retry_after=wait)

        waits: list[int] = []
        for position, model in enumerate(available):
            max_wait = LAST_RESORT_WAIT_SECONDS if position == len(available) - 1 else SHORT_WAIT_SECONDS
            for attempt in range(settings.llm_max_retries + 1):
                try:
                    reply = self._complete_with_salvage(model, messages, tools)
                    reply["model"] = model
                    reply["fallback"] = model != self.models[0]
                    return reply
                except _RateLimited as limit:
                    seconds = limit.seconds or 5
                    if seconds <= max_wait and attempt < settings.llm_max_retries:
                        logger.info("Limite par minute sur %s : attente de %d s", model, seconds)
                        time.sleep(seconds)
                        continue
                    # Quota épuisé (ou attentes répétées) : modèle mis de côté, on passe au suivant
                    self._exhausted_until[model] = time.monotonic() + seconds
                    waits.append(seconds)
                    logger.warning("Quota atteint pour %s (%d s) : bascule vers le modèle suivant", model, seconds)
                    break
        wait = min(waits) if waits else None
        raise LLMUnavailable(
            "Le service d'analyse est momentanément saturé"
            + (f" : réessayez dans {wait} s." if wait else ", réessayez dans un instant."),
            retry_after=wait,
        )

    def _complete_with_salvage(self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            return self._complete_once(model, messages, tools)
        except openai.BadRequestError as e:
            code = _error_code(e)
            text = _failed_generation(e)
            # gpt-oss rédige parfois sa réponse finale en texte (Markdown, bloc ```sql) au lieu
            # d'appeler un outil ; Groq la rejette alors (400 « tool_use_failed ») mais la renvoie.
            # On la transmet comme une réponse en texte : l'orchestrateur en extrait le SQL et le
            # soumet aux mêmes vérifications qu'un appel à repondre.
            if code == "tool_use_failed" and text.strip():
                logger.info("Réponse en texte récupérée après tool_use_failed (%d caractères)", len(text))
                return {"content": text, "tool_calls": [], "usage": None}
            logger.warning("Requête refusée par l'API du modèle (400, code=%s)", code)
            raise LLMUnavailable("Le modèle n'a pas pu formuler sa réponse, réessayez ou reformulez la question.") from None

    def _complete_once(self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=settings.llm_tool_choice,
                temperature=0.1,
                max_tokens=settings.llm_max_output_tokens,
            )
        except openai.BadRequestError:
            raise
        except openai.RateLimitError as e:
            retry = e.response.headers.get("retry-after") if e.response is not None else None
            seconds = int(float(retry)) + 1 if retry and retry.replace(".", "", 1).isdigit() else None
            logger.warning("Limite de débit atteinte pour %s (retry-after=%s)", model, retry)
            raise _RateLimited(seconds) from None
        except openai.AuthenticationError:
            logger.error("Clé de l'API du modèle refusée (LLM_API_KEY)")
            raise LLMUnavailable("Le service d'analyse est mal configuré (clé refusée).") from None
        except (openai.APIConnectionError, openai.APITimeoutError):
            logger.error("API du modèle injoignable ou trop lente")
            raise LLMUnavailable("Le service d'analyse est momentanément indisponible, réessayez plus tard.") from None
        except openai.APIError as e:
            logger.error("Erreur de l'API du modèle : %s (HTTP %s, code=%s)", type(e).__name__,
                         getattr(e, "status_code", None), _error_code(e) if isinstance(e, openai.APIStatusError) else None)
            raise LLMUnavailable("Le service d'analyse est momentanément indisponible, réessayez plus tard.") from None

        message = response.choices[0].message
        return {
            "content": message.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments or "{}"}
                for tc in (message.tool_calls or [])
            ],
            "usage": response.usage.total_tokens if response.usage else None,
        }


def _error_code(e: openai.APIStatusError) -> str | None:
    body = e.body if isinstance(e.body, dict) else {}
    error = body.get("error", body) if isinstance(body.get("error", body), dict) else {}
    return error.get("code") or getattr(e, "code", None)


def _failed_generation(e: openai.APIStatusError) -> str:
    """Texte que le modèle a tenté de produire (Groq le renvoie en cas de tool_use_failed)."""
    body = e.body if isinstance(e.body, dict) else {}
    error = body.get("error", body) if isinstance(body.get("error", body), dict) else {}
    return str(error.get("failed_generation") or "")[:8000]


_client: OpenAICompatibleClient | None = None


def get_llm_client() -> ChatClient:
    """Dépendance FastAPI ; remplacée par un faux client dans les tests."""
    global _client
    if _client is None:
        _client = OpenAICompatibleClient()
    return _client
