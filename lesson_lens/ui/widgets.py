"""Small reusable pieces of the window."""
import math

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .style import METER_FILL, METER_TRACK

# A meter above this counts as "heard something": normal speech, not room hiss.
HEARD_LEVEL = 0.35


class LevelMeter(QWidget):
    """A bar showing how loud one side is, falling back slowly like a real meter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(14)
        self.setMinimumWidth(120)
        self._level = 0.0
        self.heard = False
        # Loopback sends nothing at all while the PC is silent, so the bar has to fall on its own.
        self._fall = QTimer(self, interval=80, timeout=self._decay)
        self._fall.start()

    def reset(self):
        self._level, self.heard = 0.0, False
        self.update()

    def set_loudness(self, rms):
        """rms: loudness of the latest audio, 0-1. Shown on a -60 dB .. -10 dB scale."""
        db = 20 * math.log10(max(rms, 1e-6))
        level = min(1.0, max(0.0, (db + 60) / 50))
        self._level = max(level, self._level)
        self.heard = self.heard or level >= HEARD_LEVEL
        self.update()

    def _decay(self):
        if self._level > 0:
            self._level = max(0.0, self._level - 0.06)
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(METER_TRACK))
        p.drawRoundedRect(rect, radius, radius)
        if self._level > 0.01:
            filled = QRectF(rect.x(), rect.y(), max(rect.height(), rect.width() * self._level), rect.height())
            p.setBrush(QColor(METER_FILL))
            p.drawRoundedRect(filled, radius, radius)


class MeterPair(QWidget):
    """The two level meters: "You" and "Your student"."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.teacher = LevelMeter()
        self.student = LevelMeter()
        for label, meter in (("🎤  You", self.teacher), ("🔊  Your student", self.student)):
            row = QHBoxLayout()
            name = QLabel(label)
            name.setFixedWidth(120)
            row.addWidget(name)
            row.addWidget(meter, 1)
            layout.addLayout(row)

    def set_level(self, speaker, rms):
        (self.teacher if speaker == "teacher" else self.student).set_loudness(rms)

    def reset(self):
        self.teacher.reset()
        self.student.reset()


def friendly_error(error):
    """What to tell a teacher about an exception from Ollama, Word or the disk."""
    from ..llm import OllamaError, OllamaNotRunning

    if isinstance(error, OllamaNotRunning):
        return ("The AI helper (Ollama) isn't running.\n\n"
                "Open Ollama from the Start menu, wait a few seconds, then try again.")
    if isinstance(error, OllamaError):
        return f"The AI helper had a problem:\n\n{error}\n\nPlease try again."
    if isinstance(error, PermissionError):
        return "The feedback is open in Word.\n\nClose it in Word, then try again."
    if isinstance(error, FileNotFoundError):
        return f"A file is missing:\n\n{error.filename}"
    return f"Something went wrong:\n\n{error}"


def card():
    """A white rounded panel. Returns (frame, its vertical layout)."""
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    return frame, layout


def label(text, name=None, wrap=True):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def page():
    """An empty page with the app background. Returns (widget, its vertical layout)."""
    widget = QWidget()
    widget.setObjectName("page")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(28, 22, 28, 22)
    layout.setSpacing(14)
    return widget, layout
