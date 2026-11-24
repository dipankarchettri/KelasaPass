"""ElevenLabs speech-to-text (Scribe) and text-to-speech wrappers.

Model IDs come from env vars; take them from the ElevenLabs docs. Kannada TTS
needs an Eleven v3/v4 model. Without a key the app falls back to text.
"""
import os

import requests

API = "https://api.elevenlabs.io/v1"


def enabled() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_STT_MODEL"))


def tts_enabled() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_TTS_MODEL") and os.getenv("ELEVENLABS_VOICE_ID"))


def transcribe(audio: bytes, filename: str = "note.ogg", content_type: str = "audio/ogg") -> str:
    r = requests.post(
        f"{API}/speech-to-text",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        files={"file": (filename, audio, content_type)},
        data={"model_id": os.environ["ELEVENLABS_STT_MODEL"]},
        timeout=60,
    )
    r.raise_for_status()
    return r.json().get("text", "")


def speak(text: str) -> bytes:
    r = requests.post(
        f"{API}/text-to-speech/{os.environ['ELEVENLABS_VOICE_ID']}",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept": "audio/mpeg"},
        json={"text": text, "model_id": os.environ["ELEVENLABS_TTS_MODEL"]},
        timeout=60,
    )
    r.raise_for_status()
    return r.content
