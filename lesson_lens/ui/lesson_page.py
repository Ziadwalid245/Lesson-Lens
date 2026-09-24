"""The lesson in progress: a timer, the two level meters, and one big "End lesson" button."""
import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..pipeline import fmt_time, run_lesson
from ..regenerate import regenerate_folder
from .tasks import run_task
from .widgets import MeterPair, card, friendly_error, label


class LessonPage(QWidget):
    feedback_ready = Signal(str)  # lesson folder
    back_home = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.thread = None
        self.stop_flag = None
        self.status = queue.Queue()
        self.lesson_dir = None
        self.recording_since = None
        self._poll = QTimer(self, interval=50, timeout=self._poll_status)
        self._clock = QTimer(self, interval=500, timeout=self._tick)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        self.title = label("Lesson", "title")
        header.addWidget(self.title, 1)
        self.rec_dot = label("●", "recDot", wrap=False)
        header.addWidget(self.rec_dot)
        self.timer = label("00:00", "timer", wrap=False)
        header.addWidget(self.timer)
        layout.addLayout(header)
        self.state = label("", "subtitle")
        layout.addWidget(self.state)

        self.banner = label("", "banner")
        self.banner.hide()
        layout.addWidget(self.banner)

        sound_card, sound = card()
        sound.addWidget(label("Sound", "h2"))
        self.meters = MeterPair()
        sound.addWidget(self.meters)
        layout.addWidget(sound_card)

        words_card, words = card()
        words.addWidget(label("What Lesson Lens is hearing", "h2"))
        words.addWidget(label("Lines appear a few seconds after they're said. They don't need to be perfect.", "hint"))
        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setFont(QFont("Segoe UI", 9))
        words.addWidget(self.transcript)
        layout.addWidget(words_card, 1)

        # Shown after "End lesson": what's happening now.
        self.finishing = QProgressBar()
        self.finishing.setRange(0, 0)
        self.finishing.setTextVisible(False)
        self.finishing.setFixedHeight(8)
        self.finishing.hide()
        layout.addWidget(self.finishing)

        self.error = label("", "errorBox")
        self.error.hide()
        layout.addWidget(self.error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.retry_button = QPushButton("Try again")
        self.retry_button.setObjectName("primary")
        self.retry_button.clicked.connect(self._retry)
        self.home_button = QPushButton("Back to home")
        self.home_button.clicked.connect(self.back_home)
        self.end_button = QPushButton("■   End lesson")
        self.end_button.setObjectName("danger")
        self.end_button.clicked.connect(self.end)
        for button in (self.retry_button, self.home_button, self.end_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)

    # --- Running a lesson ------------------------------------------------------------------------
    def start(self, whisper, mic_index, speakers, student):
        self.title.setText(f"Lesson with {student}" if student else "Lesson")
        self.lesson_dir = None
        self.recording_since = None
        self.timer.setText("00:00")
        self.rec_dot.hide()
        self.state.setText("Getting ready...")
        self.banner.hide()
        self.error.hide()
        self.finishing.hide()
        self.retry_button.hide()
        self.home_button.hide()
        self.end_button.show()
        self.end_button.setEnabled(True)
        self.transcript.clear()
        self.meters.reset()

        self.status = queue.Queue()
        self.stop_flag = threading.Event()
        self.thread = threading.Thread(
            target=run_lesson, name="lesson",
            args=(self.stop_flag, self.status, whisper, mic_index, speakers, student),
            daemon=True,
        )
        self.thread.start()
        self._poll.start()

    def is_running(self):
        return self.thread is not None and self.thread.is_alive()

    def end(self):
        if self.stop_flag:
            self.stop_flag.set()
        self.end_button.setEnabled(False)
        self._clock.stop()
        self.rec_dot.hide()
        self.finishing.show()
        self.state.setText("Finishing the transcript...")

    def _tick(self):
        if self.recording_since is not None:
            self.timer.setText(fmt_time(time.monotonic() - self.recording_since))

    def _poll_status(self):
        while not self.status.empty():
            kind, value = self.status.get()
            if kind == "level":
                self.meters.set_level(*value)
            elif kind == "line":
                self.transcript.appendPlainText(
                    value.replace("] teacher: ", "]  You:  ", 1).replace("] student: ", "]  Student:  ", 1))
            elif kind == "started":
                self.lesson_dir = Path(value)
            elif kind == "info":
                self._info(value)
            elif kind == "warning":
                self.banner.setText(f"⚠️  {value}")
                self.banner.show()
            elif kind == "error":
                self._failed(value)
            elif kind == "done":
                self._poll.stop()
                self.feedback_ready.emit(value)
        if self.thread is not None and not self.thread.is_alive() and self.status.empty():
            self._poll.stop()

    def _info(self, text):
        if text == "Recording":
            self.recording_since = time.monotonic()
            self.rec_dot.show()
            self._clock.start()
            self.state.setText("Recording. Teach as normal, then press \"End lesson\".")
        elif text == "Writing feedback...":
            self.state.setText("Writing feedback... this usually takes about a minute.")
        else:
            self.state.setText(text)

    def _failed(self, message):
        self._clock.stop()
        self.rec_dot.hide()
        self.finishing.hide()
        self.end_button.hide()
        self.state.setText("The lesson didn't finish.")
        self.error.setText(message)
        self.error.show()
        self.home_button.show()
        can_retry = self.lesson_dir is not None and (self.lesson_dir / "transcript.txt").exists()
        self.retry_button.setVisible(can_retry)

    def _retry(self):
        folder = self.lesson_dir
        self.error.hide()
        self.retry_button.hide()
        self.home_button.hide()
        self.finishing.show()
        self.state.setText("Writing feedback... this usually takes about a minute.")

        def failed(error):
            self._failed(friendly_error(error))

        run_task(lambda report: regenerate_folder(folder, lambda msg: None), name="retry",
                 on_done=lambda _: self.feedback_ready.emit(str(folder)), on_error=failed)
