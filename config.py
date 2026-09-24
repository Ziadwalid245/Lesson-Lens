"""All the knobs in one place. Change a value here, restart the app, done."""
from pathlib import Path

from platformdirs import user_documents_dir

APP_NAME = "Lesson Lens"

# Every lesson gets its own folder in here: Documents\Lesson Lens\2026-09-24_15-30-00\
LESSONS_DIR = Path(user_documents_dir()) / APP_NAME

# --- Local AI (Ollama) -------------------------------------------------------
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL = "llama3.1"          # any model from ollama.com/library, e.g. "gemma4:e4b"
LLM_TEMPERATURE = 0.3           # lower = more consistent feedback
MIN_CONTEXT = 8192              # tokens; Ollama's own default is only 4096 on most PCs
MAX_CONTEXT = 32768             # raise only if you have lots of RAM/VRAM

# --- Transcription (faster-whisper) ------------------------------------------
WHISPER_MODEL = "medium"        # "medium.en" is usually a bit better for English-only lessons
VERBATIM_MODE = False           # True = nudge Whisper to keep "um", "uh" and learner errors (test it first!)
VERBATIM_PROMPT = "Umm, so I, uh... I goed to the market yesterday and, like, buyed some apple."

# --- Voice activity detection ------------------------------------------------
VAD_THRESHOLD = 0.5             # 0-1: how sure the VAD must be that a frame is speech
SILENCE_SECONDS = 2.5           # pause length that ends a speech segment
