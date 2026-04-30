from openai import OpenAI

from settings import settings
from services.utils import with_retry

_client = OpenAI(api_key=settings.openai_api_key)


def transcribe(audio_path: str) -> str:
    """Transcribe a voice file (OGG/WAV/MP3) using Whisper. Returns plain text."""

    def _call():
        with open(audio_path, "rb") as f:
            result = _client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=settings.voice_language,
                response_format="text",
                # Prompt Whisper with domain context to improve accuracy on
                # electrical-materials vocabulary (MCB, RCCB, wire gauge, etc.)
                prompt=(
                    "Electrical shop sales: MCB, RCCB, wire, cable, switch, "
                    "socket, conduit, earthing, meter, coil, piece, box."
                ),
            )
        return result.strip()

    return with_retry(_call, retries=2)
