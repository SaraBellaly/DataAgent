"""
Voix -> texte (Whisper) avec un faux moteur : aucun appel réseau, aucun quota consommé.
"""
import pytest

from app.agent.llm import LLMUnavailable
from app.agent.speech import get_stt_client
from app.main import app
from tests.test_agent_flow import user  # noqa: F401 (fixture)

pytestmark = pytest.mark.integration
AUDIO = b"\x1aE\xdf\xa3" + b"\x00" * 4000   # en-tête WebM + contenu factice


class FakeSTT:
    def __init__(self, result):
        self.result, self.calls = result, []

    def transcribe(self, audio, filename, content_type):
        self.calls.append((len(audio), filename, content_type))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def use_stt():
    def install(fake):
        app.dependency_overrides[get_stt_client] = lambda: fake
        return fake
    yield install
    app.dependency_overrides.pop(get_stt_client, None)


def send(client, data=AUDIO, content_type="audio/webm;codecs=opus"):
    return client.post("/api/voice/transcribe", files={"audio": ("q.webm", data, content_type)})


def test_transcription(user, use_stt):
    fake = use_stt(FakeSTT("Quel est le prix moyen au m² à Bordeaux ?"))
    r = send(user)
    assert r.status_code == 200 and r.json()["texte"] == "Quel est le prix moyen au m² à Bordeaux ?"
    assert fake.calls == [(len(AUDIO), "question.webm", "audio/webm")]


def test_format_refuse(user, use_stt):
    use_stt(FakeSTT("x"))
    assert send(user, content_type="image/png").status_code == 415


def test_trop_court_ou_trop_long(user, use_stt, monkeypatch):
    use_stt(FakeSTT("x"))
    assert send(user, data=b"abc").status_code == 400
    from app.core.config import settings
    monkeypatch.setattr(settings, "stt_max_bytes", 2000)
    assert send(user).status_code == 413


def test_moteur_indisponible(user, use_stt):
    use_stt(FakeSTT(LLMUnavailable("La transcription est momentanément saturée, réessayez dans un instant.")))
    r = send(user)
    assert r.status_code == 503 and "saturée" in r.json()["detail"]


def test_transcription_sans_session(client):
    assert send(client).status_code == 401
