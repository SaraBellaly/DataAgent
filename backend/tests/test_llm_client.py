"""
Client du modèle : traduction des erreurs du fournisseur (fiche, Q10), sans appel réseau.
"""
import httpx
import openai
import pytest

from app.agent.llm import LLMUnavailable, OpenAICompatibleClient

REQUEST = httpx.Request("POST", "https://api.example.test/v1/chat/completions")


def make_client(monkeypatch, exc):
    client = OpenAICompatibleClient()

    def raise_exc(**kwargs):
        raise exc

    monkeypatch.setattr(client._client.chat.completions, "create", raise_exc)
    return client


def test_tool_use_failed_recupere_le_texte(monkeypatch):
    body = {"error": {"code": "tool_use_failed", "failed_generation": "**Explication**\n```sql\nSELECT 1\n```"}}
    exc = openai.BadRequestError("tool_use_failed", response=httpx.Response(400, request=REQUEST), body=body)
    reply = make_client(monkeypatch, exc).complete([], [])
    assert reply["tool_calls"] == [] and "SELECT 1" in reply["content"]


def test_autre_erreur_400(monkeypatch):
    exc = openai.BadRequestError("bad", response=httpx.Response(400, request=REQUEST), body={"error": {"code": "x"}})
    with pytest.raises(LLMUnavailable, match="n'a pas pu formuler"):
        make_client(monkeypatch, exc).complete([], [])


def test_limite_de_debit_avec_delai(monkeypatch):
    response = httpx.Response(429, request=REQUEST, headers={"retry-after": "11"})
    exc = openai.RateLimitError("rate", response=response, body=None)
    with pytest.raises(LLMUnavailable) as info:
        make_client(monkeypatch, exc).complete([], [])
    assert info.value.retry_after == 12 and "saturé" in str(info.value)


def test_cle_refusee(monkeypatch):
    exc = openai.AuthenticationError("auth", response=httpx.Response(401, request=REQUEST), body=None)
    with pytest.raises(LLMUnavailable, match="mal configuré"):
        make_client(monkeypatch, exc).complete([], [])


def test_api_injoignable(monkeypatch):
    with pytest.raises(LLMUnavailable, match="indisponible"):
        make_client(monkeypatch, openai.APIConnectionError(request=REQUEST)).complete([], [])
