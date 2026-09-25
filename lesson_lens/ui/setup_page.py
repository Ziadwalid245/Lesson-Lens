"""First screen: gets the AI helper and the speech engine ready, fixing what it can by itself."""
import webbrowser

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .. import settings
from ..diskspace import NotEnoughSpace
from ..llm import DOWNLOAD_PAGE, OllamaNotRunning, check_ollama, ensure_model, ollama_app_path, start_ollama
from ..speech import load_whisper
from .tasks import run_task
from .widgets import card, label


class StepRow(QWidget):
    """One line of the checklist: status icon, what it is, what's happening."""

    def __init__(self, title):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.icon = QLabel("⏳")
        self.icon.setFixedWidth(28)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label(title, "h2"))
        self.detail = label("Waiting...", "hint")
        text.addWidget(self.detail)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.hide()
        text.addWidget(self.bar)
        layout.addWidget(self.icon)
        layout.addLayout(text, 1)

    def working(self, detail, percent=None):
        self.icon.setText("⏳")
        self.detail.setText(detail)
        self.bar.setVisible(True)
        if percent is None:
            self.bar.setRange(0, 0)  # moving "busy" bar
        else:
            self.bar.setRange(0, 100)
            self.bar.setValue(percent)

    def finished(self, detail):
        self.icon.setText("✅")
        self.detail.setText(detail)
        self.bar.hide()

    def problem(self, detail):
        self.icon.setText("⚠️")
        self.detail.setText(detail)
        self.bar.hide()


def _prepare_ai(report):
    try:
        check_ollama()
    except OllamaNotRunning:
        if ollama_app_path() is None:
            raise
        report(("busy", "Starting the AI helper for you..."))
        start_ollama()
    report(("busy", "Checking the AI model..."))
    ensure_model(
        on_progress=lambda msg: None,
        on_percent=lambda pct: report(("percent", pct)),
    )


class SetupPage(QWidget):
    ready = Signal(object)  # the loaded Whisper model

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.whisper = None
        self.ai_ready = False
        self._ai_running = self._speech_running = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.addStretch(1)
        box, layout = card()
        box.setMaximumWidth(620)
        layout.addWidget(label("Getting Lesson Lens ready", "title"))
        layout.addWidget(label("This takes a few seconds. The very first time it downloads what it needs, "
                               "which can take a while.", "subtitle"))
        self.ai_row = StepRow("AI helper")
        self.speech_row = StepRow("Speech engine")
        layout.addWidget(self.ai_row)
        layout.addWidget(self.speech_row)

        self.error = label("", "errorBox")
        self.error.hide()
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        self.download_button = QPushButton("Download the AI helper (Ollama)")
        self.download_button.setObjectName("primary")
        self.download_button.clicked.connect(lambda: webbrowser.open(DOWNLOAD_PAGE))
        self.retry_button = QPushButton("Try again")
        self.retry_button.clicked.connect(self.start)
        buttons.addWidget(self.download_button)
        buttons.addWidget(self.retry_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.download_button.hide()
        self.retry_button.hide()

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(box, 10)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(2)

    def start(self):
        """Run (or re-run) whichever checks haven't passed yet."""
        self.error.hide()
        self.download_button.hide()
        self.retry_button.hide()
        if not self.ai_ready and not self._ai_running:
            self._ai_running = True
            self.ai_row.working("Checking...")
            run_task(_prepare_ai, name="setup-ai",
                     on_progress=self._ai_progress, on_done=self._ai_done, on_error=self._ai_failed)
        if self.whisper is None and not self._speech_running:
            self._speech_running = True
            self.speech_row.working("Loading...")
            run_task(lambda report: load_whisper(lambda msg: report(msg)), name="setup-speech",
                     on_progress=lambda msg: self.speech_row.working(msg),
                     on_done=self._speech_done, on_error=self._speech_failed)
        self._maybe_ready()

    def recheck_ai(self):
        """After the AI model is changed in Settings."""
        self.ai_ready = False
        self.start()

    def _ai_progress(self, event):
        kind, value = event
        if kind == "percent":
            self.ai_row.working(f"Downloading the AI model (first time only): {value}%", value)
        else:
            self.ai_row.working(value)

    def _ai_done(self, _):
        self._ai_running = False
        self.ai_ready = True
        self.ai_row.finished(f"Ready ({settings.get().llm_model})")
        self._maybe_ready()

    def _ai_failed(self, error):
        self._ai_running = False
        if isinstance(error, OllamaNotRunning) and ollama_app_path() is None:
            self.ai_row.problem("Not installed yet")
            self._show_error("Lesson Lens uses a free app called Ollama to write feedback on your own computer.\n\n"
                             "1. Press the green button and install Ollama.\n"
                             "2. Come back here and press \"Try again\".")
            self.download_button.show()
        elif isinstance(error, OllamaNotRunning):
            self.ai_row.problem("Didn't start")
            self._show_error("The AI helper (Ollama) is installed but didn't start.\n\n"
                             "Open Ollama from the Start menu, wait a few seconds, then press \"Try again\".")
        elif isinstance(error, NotEnoughSpace):
            self.ai_row.problem("Not enough space")
            self._show_error(str(error))
        else:
            self.ai_row.problem("Something went wrong")
            self._show_error(f"{error}\n\nCheck your internet connection (only needed the first time) "
                             "and press \"Try again\".")
        self.retry_button.show()

    def _speech_done(self, model):
        self._speech_running = False
        self.whisper = model
        self.speech_row.finished("Ready")
        self._maybe_ready()

    def _speech_failed(self, error):
        self._speech_running = False
        if isinstance(error, NotEnoughSpace):
            self.speech_row.problem("Not enough space")
            self._show_error(str(error))
        else:
            self.speech_row.problem("Couldn't load")
            self._show_error(f"The speech engine couldn't load: {error}\n\n"
                             "Check your internet connection (only needed the first time) and press \"Try again\".")
        self.retry_button.show()

    def _show_error(self, text):
        self.error.setText(text)
        self.error.show()

    def _maybe_ready(self):
        if self.ai_ready and self.whisper is not None:
            self.ready.emit(self.whisper)
