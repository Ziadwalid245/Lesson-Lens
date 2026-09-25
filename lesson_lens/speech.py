"""Loads the Whisper speech-to-text model, once, while the app starts."""
import logging

from faster_whisper import WhisperModel
from huggingface_hub.constants import HF_HUB_CACHE

from . import settings
from .diskspace import require_free

log = logging.getLogger(__name__)


def load_whisper(on_progress=print):
    name = settings.get().whisper_model
    try:
        model = WhisperModel(name, device="cpu", compute_type="int8", local_files_only=True)
        log.info("Whisper '%s' loaded from cache", name)
        return model
    except Exception:  # not downloaded yet (the exact error depends on huggingface_hub's version)
        log.info("Whisper '%s' isn't cached, downloading it", name)
    require_free(HF_HUB_CACHE, 2, "the speech engine")
    on_progress("Downloading the speech engine (first time only, about 1.5 GB)...")
    return WhisperModel(name, device="cpu", compute_type="int8")
