"""The feedback, editable, with one-click export to Word or email."""
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QHBoxLayout, QHeaderView, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import db
from ..create_feedback import feedback_as_text, load_feedback, save_feedback
from ..feedback_structure import Correction, GrammarPoint, StudentFeedback, VocabItem
from ..regenerate import lesson_date
from .widgets import card, friendly_error, label


class TextBox(QPlainTextEdit):
    """A text box that grows with its text instead of scrolling inside the page."""

    def __init__(self, min_lines=2):
        super().__init__()
        self._min_lines = min_lines
        self.setVerticalScrollBarPolicy(self.verticalScrollBarPolicy().ScrollBarAlwaysOff)
        self.textChanged.connect(self._fit)
        self._fit()

    def _fit(self):
        lines = max(self._min_lines, int(self.document().size().height()) + 1)
        self.setFixedHeight(lines * self.fontMetrics().lineSpacing() + 16)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def lines(self):
        return [line.strip(" •-\t") for line in self.toPlainText().splitlines() if line.strip(" •-\t")]


class EditableTable(QWidget):
    """A small table the teacher can type into, add rows to and remove rows from."""

    def __init__(self, headers):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().hide()
        self.table.setWordWrap(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setVerticalScrollBarPolicy(self.table.verticalScrollBarPolicy().ScrollBarAlwaysOff)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(lambda _: QTimer.singleShot(0, self._fit))
        self.table.horizontalHeader().sectionResized.connect(lambda *_: QTimer.singleShot(0, self._fit))
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        add = QPushButton("+ Add row")
        add.clicked.connect(self._add_row)
        remove = QPushButton("Remove selected row")
        remove.clicked.connect(self._remove_row)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def set_rows(self, rows):
        self.table.setRowCount(0)
        for values in rows:
            self._add_row(values)
        self._fit()

    def rows(self):
        result = []
        for r in range(self.table.rowCount()):
            values = [(self.table.item(r, c).text().strip() if self.table.item(r, c) else "")
                      for c in range(self.table.columnCount())]
            if any(values):
                result.append(values)
        return result

    def _add_row(self, values=None):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c in range(self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem(values[c] if values else ""))
        self._fit()

    def _remove_row(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self._fit()

    def _fit(self):
        self.table.resizeRowsToContents()
        for r in range(self.table.rowCount()):  # resizeRowsToContents ignores the cell padding
            self.table.setRowHeight(r, self.table.rowHeight(r) + 10)
        height = self.table.horizontalHeader().height() + 6
        height += sum(self.table.rowHeight(r) for r in range(self.table.rowCount()))
        self.table.setFixedHeight(max(height, self.table.horizontalHeader().height() + 36))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit)


class FeedbackPage(QWidget):
    back_home = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.folder = None
        self.date = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 16)
        outer.setSpacing(10)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        self.title = label("Feedback", "title")
        self.subtitle = label("", "subtitle")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        back = QPushButton("← Back to lessons")
        back.clicked.connect(self.back_home)
        header.addWidget(back)
        outer.addLayout(header)
        outer.addWidget(label("Everything below is written by the AI and you can change any of it. "
                              "Press \"Save and open in Word\" when you're happy.", "hint"))

        body = QWidget()
        body.setObjectName("page")
        sections = QVBoxLayout(body)
        sections.setContentsMargins(0, 0, 8, 0)
        sections.setSpacing(12)

        def section(title, widget, hint=None):
            box, layout = card()
            layout.addWidget(label(title, "h2"))
            if hint:
                layout.addWidget(label(hint, "hint"))
            layout.addWidget(widget)
            sections.addWidget(box)
            return widget

        self.summary = section("What we covered", TextBox(3))
        self.did_well = section("What you did well", TextBox(3), "One point per line.")
        self.grammar = section("Grammar", EditableTable(["Grammar point", "Form", "Usage"]))
        self.vocab = section("Vocabulary", EditableTable(["Word", "Meaning", "From the lesson"]))
        self.corrections = section("Corrections", EditableTable(["What you said", "Better", "Why"]))
        self.work_on = section("What to work on", TextBox(2), "One point per line.")
        self.practice = section("Practice before our next lesson", TextBox(2))
        sections.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        save = QPushButton("Save and open in Word")
        save.setObjectName("primary")
        save.clicked.connect(self._save_and_open)
        copy = QPushButton("Copy for email or WhatsApp")
        copy.clicked.connect(self._copy)
        folder = QPushButton("Open lesson folder")
        folder.clicked.connect(lambda: os.startfile(self.folder))
        self.saved = label("", "hint", wrap=False)
        for widget in (save, copy, folder):
            buttons.addWidget(widget)
        buttons.addSpacing(8)
        buttons.addWidget(self.saved)
        buttons.addStretch(1)
        outer.addLayout(buttons)

    def show_lesson(self, folder):
        self.folder = Path(folder)
        self.date = lesson_date(self.folder)
        lesson = db.lesson_for_folder(self.folder)
        student = lesson["student_name"] if lesson is not None else None
        self.title.setText(f"Feedback for {student}" if student else "Feedback")
        started = datetime.fromisoformat(lesson["started_at"]) if lesson is not None else None
        self.subtitle.setText(started.strftime("%A %d %B %Y, %H:%M") if started else self.date.strftime("%A %d %B %Y"))
        self.saved.setText("")

        feedback = load_feedback(self.folder)
        if feedback is None:
            QMessageBox.warning(self, "Lesson Lens", "This lesson has no feedback to show yet.")
            self.back_home.emit()
            return
        self.summary.setPlainText(feedback.lesson_summary)
        self.did_well.setPlainText("\n".join(feedback.positive_feedback))
        self.grammar.set_rows([[g.name, g.form, g.usage] for g in feedback.grammar_points])
        self.vocab.set_rows([[v.word, v.definition, v.in_context] for v in feedback.vocab_items])
        self.corrections.set_rows([[c.original, c.corrected, c.explanation] for c in feedback.corrections])
        self.work_on.setPlainText("\n".join(feedback.improvement_areas))
        self.practice.setPlainText(feedback.practice_task)

    def collect(self):
        """The feedback as it is on screen now, including the teacher's edits."""
        return StudentFeedback(
            lesson_summary=self.summary.toPlainText().strip(),
            positive_feedback=self.did_well.lines(),
            grammar_points=[GrammarPoint(name=a, form=b, usage=c) for a, b, c in self.grammar.rows()],
            vocab_items=[VocabItem(word=a, definition=b, in_context=c) for a, b, c in self.vocab.rows()],
            corrections=[Correction(original=a, corrected=b, explanation=c) for a, b, c in self.corrections.rows()],
            improvement_areas=self.work_on.lines(),
            practice_task=self.practice.toPlainText().strip(),
        )

    def _save(self):
        """Save the edits. Returns the .docx path, or None if Word is holding it open."""
        try:
            return save_feedback(self.collect(), self.folder, self.date)
        except OSError as e:
            QMessageBox.warning(self, "Lesson Lens", friendly_error(e))
            return None

    def _save_and_open(self):
        docx = self._save()
        if docx:
            self.saved.setText("✅  Saved")
            os.startfile(docx)

    def _copy(self):
        feedback = self.collect()
        QApplication.clipboard().setText(feedback_as_text(feedback, self.date))
        self.saved.setText("✅  Copied. Paste it into your email or chat.")
        try:
            save_feedback(feedback, self.folder, self.date)  # keep the edits too
        except OSError:
            pass  # feedback.json is saved first; only the .docx couldn't be updated
