"""Help: the how-to guide, and a problem report the teacher can paste into a message."""
import os
import platform
import re
import webbrowser

from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QPushButton, QVBoxLayout

from .. import HOMEPAGE, SUPPORT_EMAIL, SUPPORT_URL, __version__, db, paths, settings
from .widgets import label


def problem_report():
    """Version, settings and the end of the log, with student names blanked out.

    The log never contains what was said in a lesson, but lesson folder names include the student.
    """
    cfg = settings.get()
    header = [
        f"Lesson Lens {__version__} on Windows {platform.version()}",
        f"AI model: {cfg.llm_model} | Speech: {cfg.whisper_model} | Save audio: {cfg.save_audio}",
        "",
        "--- Log (last 150 lines) ---",
    ]
    try:
        log_lines = paths.LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-150:]
    except OSError:
        log_lines = ["(no log file yet)"]
    text = "\n".join(header + log_lines)
    for name in sorted(db.student_names(), key=len, reverse=True):
        text = re.sub(re.escape(name), "[student]", text, flags=re.IGNORECASE)
    return text


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(label("How to use Lesson Lens", "h2"))
        layout.addWidget(label("A short step-by-step guide with pictures.", "hint"))
        guide = QPushButton("Open the guide")
        guide.clicked.connect(lambda: webbrowser.open(HOMEPAGE))
        layout.addWidget(guide)

        layout.addSpacing(8)
        layout.addWidget(label("Something not working?", "h2"))
        layout.addWidget(label(
            "1. Press \"Copy problem report\".\n"
            f"2. Email it to {SUPPORT_EMAIL}: paste the report into the email, "
            "with a sentence about what happened.\n\n"
            "The report has technical details only: nothing that was said in your lessons, and no student names.",
            "hint"))
        buttons = QHBoxLayout()
        copy = QPushButton("Copy problem report")
        copy.setObjectName("primary")
        copy.clicked.connect(self._copy)
        email = QPushButton("Email us")
        email.clicked.connect(lambda: webbrowser.open(SUPPORT_URL))
        copy_address = QPushButton("Copy email address")
        copy_address.clicked.connect(self._copy_address)
        logs = QPushButton("Open log folder")
        logs.clicked.connect(lambda: os.startfile(paths.LOG_DIR))
        for button in (copy, email, copy_address, logs):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.copied = label("", "hint")
        layout.addWidget(self.copied)

        layout.addSpacing(8)
        close_row = QHBoxLayout()
        close_row.addWidget(label(f"Lesson Lens {__version__}", "hint"), 1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        close_row.addWidget(close)
        layout.addLayout(close_row)

    def _copy(self):
        QApplication.clipboard().setText(problem_report())
        self.copied.setText(f"✅  Copied. Now paste it into an email to {SUPPORT_EMAIL}.")

    def _copy_address(self):
        QApplication.clipboard().setText(SUPPORT_EMAIL)
        self.copied.setText(f"✅  Copied {SUPPORT_EMAIL}. Paste it into the \"To\" box of a new email.")
