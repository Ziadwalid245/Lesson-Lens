"""Re-create the feedback for a lesson from its saved transcript.

Use it when Ollama was off during the lesson, or to test prompt changes:
    python -m lesson_lens regenerate "C:\\Users\\you\\Documents\\Lesson Lens\\2026-09-24_15-30-00\\transcript.txt"
"""
import logging
import sys
from datetime import date, datetime

from . import db
from .create_feedback import create_feedback_doc
from .llm import OllamaError, ensure_model, generate_feedback

log = logging.getLogger(__name__)


def regenerate_command(transcript_path):
    """The command a teacher can paste to regenerate this lesson, for the .exe or from source."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" regenerate "{transcript_path}"'
    return f'python -m lesson_lens regenerate "{transcript_path}"'


def _lesson_date(folder):
    """The date the lesson was taught, from its folder name (2026-09-24_15-30-00)."""
    try:
        return datetime.strptime(folder.name[:10], "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def regenerate(transcript_path):
    """Returns a process exit code: 0 on success."""
    try:
        # utf-8-sig: PowerShell's Out-File adds a byte-order mark the AI would otherwise see.
        transcript = transcript_path.read_text(encoding="utf-8-sig")
    except OSError as e:
        print(f"Couldn't read the transcript: {e}")
        return 1

    log.info("Regenerating feedback for %s", transcript_path)
    try:
        ensure_model(print)
        feedback = generate_feedback(transcript, print)
    except OllamaError as e:
        log.warning("Regenerate failed: %s", e)
        print(f"\n{e}")
        return 1

    out = transcript_path.with_name("feedback.docx")
    try:
        create_feedback_doc(feedback, out, _lesson_date(transcript_path.parent))
    except PermissionError:
        print(f"\nCouldn't save {out}.\nIt's probably open in Word: close it and run this again.")
        return 1

    lesson = db.lesson_for_folder(transcript_path.parent)
    if lesson is not None:
        db.set_status(lesson["id"], "done")
    print(f"\nSaved: {out}")
    return 0
