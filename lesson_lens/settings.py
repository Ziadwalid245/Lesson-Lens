"""All the knobs in one place.

The defaults live here. To change one on this PC, put it in
%APPDATA%\\Lesson Lens\\settings.json, e.g.  {"llm_model": "gemma4:e4b", "save_audio": false}
then restart the app. Only the values you write there change; everything else
keeps following the defaults below, so future updates still reach you.
"""
import json
import logging
import os
from dataclasses import dataclass, fields
from functools import cache
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)


@dataclass
class Settings:
    # --- Lessons -----------------------------------------------------------------
    # Every lesson gets its own folder in here: <lessons_dir>\2026-09-24_15-30-00\
    lessons_dir: str = str(paths.DEFAULT_LESSONS_DIR)
    save_audio: bool = True         # teacher.wav + student.wav per lesson, ~85 MB per side per 45 min

    # --- Local AI (Ollama) -------------------------------------------------------
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "llama3.1"     # any model from ollama.com/library, e.g. "gemma4:e4b"
    llm_temperature: float = 0.3    # lower = more consistent feedback
    min_context: int = 8192         # tokens; Ollama's own default is only 4096 on most PCs
    max_context: int = 32768        # raise only if you have lots of RAM/VRAM

    # --- Transcription (faster-whisper) ------------------------------------------
    whisper_model: str = "medium"   # "medium.en" is usually a bit better for English-only lessons
    verbatim_mode: bool = False     # True = nudge Whisper to keep "um", "uh" and learner errors (test it first!)
    verbatim_prompt: str = "Umm, so I, uh... I goed to the market yesterday and, like, buyed some apple."

    # --- Voice activity detection ------------------------------------------------
    vad_threshold: float = 0.5      # 0-1: how sure the VAD must be that a frame is speech
    silence_seconds: float = 2.5    # pause length that ends a speech segment

    # --- Remembered by the app (you don't need to set these) ---------------------
    last_microphone: str = ""
    last_speakers: str = ""
    last_student: str = ""

    @property
    def lessons_path(self):
        return Path(os.path.expandvars(self.lessons_dir)).expanduser()


_DEFAULTS = Settings()
_NAMES = {f.name for f in fields(Settings)}


def _read_file():
    """The raw dict in settings.json, {} if there is none, or None if it's unreadable."""
    try:
        raw = json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log.warning("Couldn't read %s (%s). Using the default settings.", paths.SETTINGS_FILE, e)
        return None
    if not isinstance(raw, dict):
        log.warning("%s should contain a JSON object {...}. Using the default settings.", paths.SETTINGS_FILE)
        return None
    return raw


def _checked(name, value):
    """value converted to the setting's type, or None (with a log line) if it's the wrong kind."""
    expected = type(getattr(_DEFAULTS, name))
    if expected is float and type(value) is int:
        return float(value)
    if type(value) is expected:
        return value
    log.warning("Ignoring %s=%r in settings.json: it should be a %s.", name, value, expected.__name__)
    return None


@cache
def get():
    """The settings for this run: the defaults, overridden by settings.json."""
    current = Settings()
    for name, value in (_read_file() or {}).items():
        if name not in _NAMES:
            log.warning("Unknown setting %r in settings.json (typo?). The known ones are in settings.py.", name)
            continue
        value = _checked(name, value)
        if value is not None:
            setattr(current, name, value)
    return current


def update(**changes):
    """Change some settings now and save just those keys to settings.json."""
    current = get()
    for name, value in changes.items():
        if name not in _NAMES:
            raise AttributeError(f"No setting called {name!r}")
        setattr(current, name, value)

    raw = _read_file()
    if raw is None:  # never overwrite a file the teacher is halfway through editing
        return
    raw.update(changes)
    paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = paths.SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    tmp.replace(paths.SETTINGS_FILE)
