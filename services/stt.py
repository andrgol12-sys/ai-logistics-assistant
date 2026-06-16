"""
Speech-to-Text Service.
Handles voice message transcription.
"""

from pathlib import Path
from typing import Any, Union

from services.openai_client import openai_client
from utils.logging import logger
from utils.helpers import convert_ogg_to_wav, cleanup_file


def normalize_transcription_result(result: Any) -> str:
    """
    Extract recognized text from STT result.

    Supports plain string, dict with text/transcription, or API response objects.
    """
    if result is None:
        return ""

    if isinstance(result, str):
        return result.strip()

    if isinstance(result, dict):
        for key in ("transcription", "text"):
            value = result.get(key)
            if value:
                return str(value).strip()
        return ""

    for attr in ("text", "transcription"):
        value = getattr(result, attr, None)
        if value:
            return str(value).strip()

    return str(result).strip()


async def transcribe_voice_message(audio_path: Union[str, Path]) -> str:
    """
    Transcribe a voice message to text.
    
    Args:
        audio_path: Path to audio file (OGG or WAV)
    
    Returns:
        Transcribed text
    """
    audio_path = Path(audio_path)
    wav_path = None
    
    try:
        transcription_path = audio_path

        # Whisper accepts OGG directly; convert only if direct transcription fails
        if audio_path.suffix.lower() == ".ogg":
            try:
                raw_result = await openai_client.transcribe_audio(audio_path)
                text = normalize_transcription_result(raw_result)
                if text:
                    logger.info(
                        f"Voice recognized ({len(text)} chars): {text[:120]}"
                        f"{'...' if len(text) > 120 else ''}"
                    )
                    return text
            except Exception as direct_error:
                logger.warning(
                    f"Direct OGG transcription failed, trying WAV conversion: {direct_error}"
                )
                wav_path = convert_ogg_to_wav(audio_path)
                transcription_path = wav_path
        else:
            transcription_path = audio_path

        raw_result = await openai_client.transcribe_audio(transcription_path)
        text = normalize_transcription_result(raw_result)

        if not text:
            raise ValueError("Speech recognition returned empty text")

        logger.info(
            f"Voice recognized ({len(text)} chars): {text[:120]}"
            f"{'...' if len(text) > 120 else ''}"
        )
        return text
        
    except Exception as e:
        logger.error(f"Error in voice transcription: {e}")
        raise
        
    finally:
        if wav_path and wav_path != audio_path:
            cleanup_file(wav_path)

