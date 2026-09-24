"""One rotating log file for the whole app, including crashes in background threads.

Transcript text is never logged: the log is for "what went wrong", not lesson content.
"""
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from . import paths

_configured = False


def setup(level=logging.INFO):
    global _configured
    if _configured:
        return
    _configured = True

    paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s")

    file_handler = RotatingFileHandler(paths.LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)

    if sys.stderr is not None:  # None in a windowed .exe
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    # faster-whisper logs every chunk at INFO; urllib3 logs every request.
    for noisy in ("faster_whisper", "urllib3", "httpx", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    def log_uncaught(exc_type, exc, tb):
        logging.getLogger("lesson_lens").critical("Uncaught error", exc_info=(exc_type, exc, tb))

    def log_uncaught_in_thread(args):
        if args.exc_type is not SystemExit:
            logging.getLogger("lesson_lens").critical(
                "Uncaught error in thread %s", args.thread.name if args.thread else "?",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

    sys.excepthook = log_uncaught
    threading.excepthook = log_uncaught_in_thread
