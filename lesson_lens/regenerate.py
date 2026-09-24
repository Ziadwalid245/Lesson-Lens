"""Re-create the feedback for a lesson from its saved transcript.

The app's "Try again" button uses this. From the command line, use it when
Ollama was off during the lesson, or to test prompt changes:
    python -m lesson_lens regenerate "C:\\Users\\you\\Documents\\Lesson Lens\\2026-09-24 15-30 Omar\\transcript.txt"
"""
import logging
from datetime import date, datetime
from pathlib import Path

from . import db
from .create_feedback import save_feedback
from .llm import OllamaError, ensure_model, generate_feedback

log = logging.getLogger(__name__)


def lesson_date(folder):
    """The date the lesson was taught: from the database, else the folder name (2026-09-24 ...)."""
    lesson = db.lesson_for_folder(folder)
    if lesson is not None:
        return datetime.fromisoformat(lesson["started_at"]).date()
    try:
        return datetime.strptime(Path(folder).name[:10], "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def regenerate_folder(folder, on_progress=print):
    """Write fresh feedback for the lesson in folder. Returns the feedback.

    Raises OllamaError, OSError (no transcript), or PermissionError (Word has the .docx open).
    """
    folder = Path(folder)
    # utf-8-sig: PowerShell's Out-File adds a byte-order mark the AI would otherwise see.
    transcript = (folder / "transcript.txt").read_text(encoding="utf-8-sig")
    log.info("Regenerating feedback for %s", folder)
    ensure_model(on_progress)
    feedback = generate_feedback(transcript, on_progress)
    save_feedback(feedback, folder, lesson_date(folder))
    lesson = db.lesson_for_folder(folder)
    if lesson is not None:
        db.set_status(lesson["id"], "done")
    return feedback


def regenerate(transcript_path):
    """Command-line version. Returns a process exit code: 0 on success."""
    folder = Path(transcript_path).parent
    try:
        regenerate_folder(folder)
    except OllamaError as e:
        log.warning("Regenerate failed: %s", e)
        print(f"\n{e}")
        return 1
    except PermissionError:
        print(f"\nCouldn't save {folder / 'feedback.docx'}.\nIt's probably open in Word: close it and run this again.")
        return 1
    except OSError as e:
        print(f"Couldn't read the transcript: {e}")
        return 1
    print(f"\nSaved: {folder / 'feedback.docx'}")
    return 0
