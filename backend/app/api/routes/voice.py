"""
Interaction vocale : transcription de la question dictée (Whisper). Le texte reconnu est renvoyé
au navigateur, qui l'affiche pour correction AVANT envoi à l'agent : rien n'est envoyé seul.
"""
import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.agent.llm import LLMUnavailable
from app.agent.speech import SpeechToText, get_stt_client
from app.api.deps import get_current_user
from app.core.config import settings
from app.schemas import Message, TranscriptionOut

router = APIRouter(prefix="/api/voice", tags=["voix"])

# Formats produits par MediaRecorder selon les navigateurs, et acceptés par Whisper
ALLOWED_TYPES = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/m4a"}


@router.post("/transcribe", response_model=TranscriptionOut,
             responses={400: {"model": Message}, 401: {"model": Message}, 413: {"model": Message},
                        415: {"model": Message}, 503: {"model": Message}})
def transcribe(audio: UploadFile = File(...), user: dict = Depends(get_current_user),
               stt: SpeechToText = Depends(get_stt_client)):
    content_type = (audio.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Format audio non pris en charge.")
    data = audio.file.read(settings.stt_max_bytes + 1)
    if len(data) > settings.stt_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"Enregistrement trop long (plus de {settings.stt_max_bytes // 1_000_000} Mo).")
    if len(data) < 1000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enregistrement vide ou trop court.")

    start = time.perf_counter()
    extension = content_type.split("/")[-1].replace("x-", "").replace("mpeg", "mp3")
    try:
        text = stt.transcribe(data, f"question.{extension}", content_type)
    except LLMUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
    return TranscriptionOut(texte=text, duree_ms=round((time.perf_counter() - start) * 1000, 1))
