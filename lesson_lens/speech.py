"""Loads the Whisper speech-to-text model, once, while the app starts."""
import logging

from faster_whisper import WhisperModel

from . import settings

log = logging.getLogger(__name__)


def load_whisper(on_progress=print):
    name = settings.get().whisper_model
    try:
        model = WhisperModel(name, device="cpu", compute_type="int8", local_files_only=True)
        log.info("Whisper '%s' loaded from cache", name)
        return model
    except Exception:  # not downloaded yet (the exact error depends on huggingface_hub's version)
        log.info("Whisper '%s' isn't cached, downloading it", name)
    on_progress("Downloading the speech engine (first time only, about 1.5 GB)...")
    return WhisperModel(name, device="cpu", compute_type="int8")
