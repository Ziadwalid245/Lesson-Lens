"""Home: pick the student, check the sound, start a lesson, and find past lessons."""
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import db, settings
from ..capture_loopback import loopback_frames
from ..capture_mic import mic_frames
from ..devices import friendly_name
from ..pipeline import metered
from ..regenerate import regenerate_folder
from .tasks import run_task
from .widgets import MeterPair, card, friendly_error, label

SOUND_CHECK_SECONDS = 15


def _listen(speaker, frames, levels):
    try:
        for _ in metered(speaker, frames, levels):
            pass
    except Exception as e:
        levels.put(("error", (speaker, str(e))))


def _describe(lesson):
    """(when, student, length, status text, action) for one row of the lesson list."""
    folder = Path(lesson["folder"])
    started = datetime.fromisoformat(lesson["started_at"])
    when = started.strftime("%a %d %b, %H:%M")
    seconds = lesson["duration_seconds"]
    length = "" if seconds is None else "<1 min" if seconds < 60 else f"{round(seconds / 60)} min"
    student = lesson["student_name"] or "—"
    has_json = (folder / "feedback.json").exists()
    if lesson["status"] == "done" and (has_json or (folder / "feedback.docx").exists()):
        return when, student, length, "✅  Feedback ready", "Open" if has_json else "Open in Word"
    if lesson["status"] == "recording":
        return when, student, length, "●  Recording now", None
    if (folder / "transcript.txt").exists():
        return when, student, length, "⚠️  Feedback not written yet", "Try again"
    return when, student, length, "✖  Nothing was recorded", None


class HomePage(QWidget):
    start_requested = Signal(str)   # student name
    open_lesson = Signal(str)       # lesson folder
    settings_requested = Signal()

    def __init__(self, current_devices):
        """current_devices() -> (mic name, mic index, speakers name, speakers info)."""
        super().__init__()
        self.setObjectName("page")
        self.current_devices = current_devices
        self._check_stop = None
        self._levels = queue.Queue()
        self._check_ends = 0.0
        self._check_errors = []
        self._poll = QTimer(self, interval=50, timeout=self._poll_levels)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.addWidget(label("Lesson Lens", "title"))
        header.addStretch(1)
        settings_button = QPushButton("⚙  Settings")
        settings_button.clicked.connect(self.settings_requested)
        header.addWidget(settings_button)
        layout.addLayout(header)

        # --- Start a lesson ---------------------------------------------------------
        start_card, start = card()
        start.addWidget(label("Who are you teaching?", "h2"))
        row = QHBoxLayout()
        self.student = QComboBox()
        self.student.setEditable(True)
        self.student.setInsertPolicy(QComboBox.NoInsert)
        self.student.lineEdit().setPlaceholderText("Type your student's name")
        row.addWidget(self.student, 1)
        self.start_button = QPushButton("▶   Start lesson")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self._start)
        row.addWidget(self.start_button)
        start.addLayout(row)

        start.addSpacing(6)
        sound_header = QHBoxLayout()
        sound_header.addWidget(label("Sound", "h2"))
        sound_header.addStretch(1)
        self.check_button = QPushButton("Check sound")
        self.check_button.clicked.connect(self.toggle_sound_check)
        sound_header.addWidget(self.check_button)
        start.addLayout(sound_header)
        self.meters = MeterPair()
        start.addWidget(self.meters)
        self.check_result = label("", "hint")
        start.addWidget(self.check_result)
        devices_row = QHBoxLayout()
        self.devices_label = label("", "hint")
        devices_row.addWidget(self.devices_label, 1)
        change = QPushButton("Change")
        change.setObjectName("link")
        change.clicked.connect(self.settings_requested)
        devices_row.addWidget(change, 0, Qt.AlignTop)
        start.addLayout(devices_row)
        layout.addWidget(start_card)

        # --- Past lessons -------------------------------------------------------------
        history_card, history = card()
        history.addWidget(label("Past lessons", "h2"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["When", "Student", "Length", "Feedback", ""])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(QHeaderView.ResizeToContents)
        head.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(lambda row, _col: self._row_action(row))
        history.addWidget(self.table)
        self.empty_history = label("Your lessons will appear here.", "hint")
        history.addWidget(self.empty_history)
        layout.addWidget(history_card, 1)

        self._lessons = []
        self.refresh()

    # --- Data -----------------------------------------------------------------------------
    def refresh(self):
        current = self.student.currentText() or settings.get().last_student
        self.student.clear()
        self.student.addItems(db.student_names())
        self.student.setCurrentText(current)
        self.refresh_devices()

        self._lessons = db.recent_lessons()
        self.table.setRowCount(len(self._lessons))
        for row, lesson in enumerate(self._lessons):
            when, student, length, status, action = _describe(lesson)
            for col, text in enumerate((when, student, length, status)):
                item = QTableWidgetItem(text)
                if col == 3 and lesson["error"]:
                    item.setToolTip(lesson["error"])
                self.table.setItem(row, col, item)
            if action:
                button = QPushButton(action)
                button.clicked.connect(lambda _=False, r=row: self._row_action(r))
                self.table.setCellWidget(row, 4, button)
            else:
                self.table.removeCellWidget(row, 4)
        self.table.setVisible(bool(self._lessons))
        self.empty_history.setVisible(not self._lessons)

    def refresh_devices(self):
        try:
            mic, _, speakers, _ = self.current_devices()
            self.devices_label.setText(f"Your microphone: {mic}\nYou hear your student on: {friendly_name(speakers)}")
        except RuntimeError as e:
            self.devices_label.setText(str(e))

    # --- Start ------------------------------------------------------------------------------
    def _start(self):
        name = self.student.currentText().strip()
        if not name:
            answer = QMessageBox.question(
                self, "Lesson Lens",
                "You haven't typed your student's name.\n\nStart anyway? (The name helps you find the lesson later.)",
            )
            if answer != QMessageBox.Yes:
                self.student.setFocus()
                return
        self.stop_sound_check()
        self.start_requested.emit(name)

    # --- Past lessons ---------------------------------------------------------------------
    def _row_action(self, row):
        lesson = self._lessons[row]
        folder = Path(lesson["folder"])
        _, _, _, _, action = _describe(lesson)
        if action == "Open":
            self.open_lesson.emit(str(folder))
        elif action == "Open in Word":
            os.startfile(folder / "feedback.docx")
        elif action == "Try again":
            self._retry(row, folder)

    def _retry(self, row, folder):
        button = self.table.cellWidget(row, 4)
        if button:
            button.setEnabled(False)
        self.table.item(row, 3).setText("⏳  Writing feedback... (about a minute)")

        def done(_):
            self.refresh()
            self.open_lesson.emit(str(folder))

        def failed(error):
            self.refresh()
            QMessageBox.warning(self, "Lesson Lens", friendly_error(error))

        run_task(lambda report: regenerate_folder(folder, lambda msg: None), name="retry",
                 on_done=done, on_error=failed)

    # --- Sound check ----------------------------------------------------------------------
    def toggle_sound_check(self):
        if self._check_stop:
            self.stop_sound_check()
            return
        try:
            _, mic_index, _, speakers = self.current_devices()
        except RuntimeError as e:
            QMessageBox.warning(self, "Lesson Lens", str(e))
            return
        self._check_stop = threading.Event()
        self._check_errors = []
        self._levels = queue.Queue()
        self.meters.reset()
        for speaker, frames in (("teacher", mic_frames(mic_index, self._check_stop)),
                                ("student", loopback_frames(speakers, self._check_stop))):
            threading.Thread(target=_listen, args=(speaker, frames, self._levels),
                             name=f"check-{speaker}", daemon=True).start()
        self._check_ends = time.monotonic() + SOUND_CHECK_SECONDS
        self.check_button.setText("Stop checking")
        self.check_result.setObjectName("hint")
        self.check_result.setText("Say something: the \"You\" bar should move.\n"
                                  "Then play a video with someone talking: the \"Your student\" bar should move.")
        self._restyle(self.check_result)
        self._poll.start()

    def stop_sound_check(self, finished=False):
        if not self._check_stop:
            return
        self._check_stop.set()
        self._check_stop = None
        self._poll.stop()
        self.check_button.setText("Check sound")
        if finished:
            self._report_check()
        else:
            self.check_result.setText("")

    def _poll_levels(self):
        while not self._levels.empty():
            kind, value = self._levels.get()
            if kind == "level":
                self.meters.set_level(*value)
            else:
                self._check_errors.append(value)
        if time.monotonic() >= self._check_ends or len(self._check_errors) == 2:
            self.stop_sound_check(finished=True)

    def _report_check(self):
        teacher_ok, student_ok = self.meters.teacher.heard, self.meters.student.heard
        errors = dict(self._check_errors)
        if teacher_ok and student_ok:
            self.check_result.setObjectName("okBox")
            self.check_result.setText("✅  Both sides are working. You're ready to start.")
        else:
            problems = []
            if not teacher_ok:
                problems.append(f"• Your microphone couldn't be opened: {errors['teacher']}" if "teacher" in errors
                                else "• Your side stayed quiet. Is the right microphone chosen, and is it unmuted?")
            if not student_ok:
                problems.append(f"• Your student's side couldn't be opened: {errors['student']}" if "student" in errors
                                else "• Your student's side stayed quiet. Was something with talking playing, "
                                     "and are you hearing it on the device shown below?")
            self.check_result.setObjectName("errorBox")
            self.check_result.setText("\n".join(problems) + "\n\nYou can change devices with \"Change\" below.")
        self._restyle(self.check_result)

    @staticmethod
    def _restyle(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
