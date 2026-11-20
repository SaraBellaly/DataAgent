"""
Voix -> texte : Whisper (whisper-large-v3) sur Groq, par l'API compatible OpenAI.

L'audio enregistré dans le navigateur passe par le backend : la clé de l'API n'est jamais
exposée au navigateur. La synthèse vocale (texte -> voix) est faite par le navigateur
(speechSynthesis), en français, sans service externe.

Découplé de l'interface : la route ne connaît que SpeechToText ; un autre moteur
(Whisper local, autre fournisseur) se branche en remplaçant get_stt_client.
"""
import logging
from typing import Protocol

import openai

from app.agent.llm import LLMUnavailable
from app.core.config import settings

logger = logging.getLogger(__name__)


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes, filename: str, content_type: str) -> str: ...


class WhisperClient:
    def __init__(self) -> None:
        self._client = openai.OpenAI(
            base_url=settings.stt_base_url or settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value() or "sans-cle",
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    def transcribe(self, audio: bytes, filename: str, content_type: str) -> str:
        try:
            result = self._client.audio.transcriptions.create(
                model=settings.stt_model,
                file=(filename, audio, content_type),
                language=settings.stt_language,
                temperature=0,
                response_format="json",
            )
        except openai.RateLimitError:
            raise LLMUnavailable("La transcription est momentanément saturée, réessayez dans un instant.") from None
        except openai.AuthenticationError:
            raise LLMUnavailable("La transcription est mal configurée (clé refusée).") from None
        except openai.APIError as e:
            logger.error("Erreur de transcription : %s (HTTP %s)", type(e).__name__, getattr(e, "status_code", None))
            raise LLMUnavailable("La transcription est momentanément indisponible, réessayez plus tard.") from None
        return (result.text or "").strip()


_client: WhisperClient | None = None


def get_stt_client() -> SpeechToText:
    """Dépendance FastAPI ; remplacée par un faux client dans les tests."""
    global _client
    if _client is None:
        _client = WhisperClient()
    return _client
