"""
Client du modèle : chaîne principal -> secours et traduction des erreurs (fiche, Q10), sans appel réseau.
"""
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.agent import llm as llm_module
from app.agent.llm import LLMUnavailable, OpenAICompatibleClient
from app.core.config import settings

REQUEST = httpx.Request("POST", "https://api.example.test/v1/chat/completions")
PRIMARY, FALLBACK = "openai/gpt-oss-120b", "openai/gpt-oss-20b"


def ok(text="réponse"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None))], usage=None)


def rate_limit(seconds):
    return openai.RateLimitError("rate", response=httpx.Response(429, request=REQUEST, headers={"retry-after": str(seconds)}), body=None)


@pytest.fixture
def client(monkeypatch):
    """Client avec la chaîne 120b -> 20b ; `script` dicte la réponse de chaque modèle, appel par appel."""
    monkeypatch.setattr(settings, "llm_model", PRIMARY)
    monkeypatch.setattr(settings, "llm_fallback_models", [FALLBACK])
    monkeypatch.setattr(settings, "llm_max_retries", 2)
    sleeps = []
    monkeypatch.setattr(llm_module.time, "sleep", lambda s: sleeps.append(s))
    c = OpenAICompatibleClient()
    c.calls, c.sleeps, c.script = [], sleeps, {}

    def create(**kwargs):
        c.calls.append(kwargs["model"])
        outcome = c.script[kwargs["model"]].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(c._client.chat.completions, "create", create)
    return c


def test_principal_utilise_en_premier(client):
    client.script = {PRIMARY: [ok()]}
    reply = client.complete([], [])
    assert client.calls == [PRIMARY] and reply["model"] == PRIMARY and reply["fallback"] is False


def test_quota_epuise_bascule_vers_le_secours(client):
    client.script = {PRIMARY: [rate_limit(900)], FALLBACK: [ok(), ok()]}
    reply = client.complete([], [])
    assert client.calls == [PRIMARY, FALLBACK] and reply["fallback"] is True and reply["model"] == FALLBACK
    assert client.sleeps == []    # aucune attente : bascule immédiate
    # Le principal épuisé est mis de côté : l'étape suivante va directement au secours
    client.complete([], [])
    assert client.calls == [PRIMARY, FALLBACK, FALLBACK]


def test_limite_courte_attendue_sur_le_meme_modele(client):
    client.script = {PRIMARY: [rate_limit(3), ok()]}
    reply = client.complete([], [])
    assert client.calls == [PRIMARY, PRIMARY] and reply["fallback"] is False
    assert client.sleeps == [4]


def test_tous_les_modeles_epuises(client):
    client.script = {PRIMARY: [rate_limit(900)], FALLBACK: [rate_limit(300)]}
    with pytest.raises(LLMUnavailable) as info:
        client.complete([], [])
    assert info.value.retry_after == 301 and "saturé" in str(info.value)
    # Les deux sont mis de côté : pas de nouvel appel, délai annoncé directement
    with pytest.raises(LLMUnavailable) as again:
        client.complete([], [])
    assert len(client.calls) == 2 and again.value.retry_after and again.value.retry_after <= 301


def test_tool_use_failed_recupere_le_texte(client):
    body = {"error": {"code": "tool_use_failed", "failed_generation": "**Explication**\n```sql\nSELECT 1\n```"}}
    client.script = {PRIMARY: [openai.BadRequestError("tool_use_failed", response=httpx.Response(400, request=REQUEST), body=body)]}
    reply = client.complete([], [])
    assert reply["tool_calls"] == [] and "SELECT 1" in reply["content"]


def test_autre_erreur_400(client):
    client.script = {PRIMARY: [openai.BadRequestError("bad", response=httpx.Response(400, request=REQUEST), body={"error": {"code": "x"}})]}
    with pytest.raises(LLMUnavailable, match="n'a pas pu formuler"):
        client.complete([], [])


def test_cle_refusee(client):
    client.script = {PRIMARY: [openai.AuthenticationError("auth", response=httpx.Response(401, request=REQUEST), body=None)]}
    with pytest.raises(LLMUnavailable, match="mal configuré"):
        client.complete([], [])


def test_api_injoignable(client):
    client.script = {PRIMARY: [openai.APIConnectionError(request=REQUEST)]}
    with pytest.raises(LLMUnavailable, match="indisponible"):
        client.complete([], [])


def test_dernier_modele_attend_une_minute_avant_de_renoncer(client):
    """Le secours n'a plus de relais : une limite par minute de 28 s est attendue plutôt qu'un échec."""
    client.script = {PRIMARY: [rate_limit(900)], FALLBACK: [rate_limit(28), ok()]}
    reply = client.complete([], [])
    assert client.calls == [PRIMARY, FALLBACK, FALLBACK] and reply["fallback"] is True
    assert client.sleeps == [29]


def test_principal_ne_patiente_pas_longtemps_s_il_existe_un_secours(client):
    client.script = {PRIMARY: [rate_limit(28)], FALLBACK: [ok()]}
    reply = client.complete([], [])
    assert client.calls == [PRIMARY, FALLBACK] and client.sleeps == [] and reply["fallback"] is True
