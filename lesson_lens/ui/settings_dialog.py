"""Settings in plain words: devices, feedback quality, audio, and where lessons go."""
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
    QPushButton, QVBoxLayout,
)

from .. import settings
from ..devices import friendly_name
from .widgets import label

QUALITY = [
    ("Best (recommended). First download: 9.6 GB", "gemma4:e4b"),
    ("Faster, but misses more mistakes. First download: 4.9 GB", "llama3.1"),
]


class SettingsDialog(QDialog):
    def __init__(self, parent, input_devices, output_devices, current_mic, current_speakers):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        cfg = settings.get()
        self.model_changed = False

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setVerticalSpacing(12)

        self.mic = QComboBox()
        self.mic.addItems(list(input_devices))
        self.mic.setCurrentText(current_mic or "")
        form.addRow("Your microphone", self.mic)

        self.speakers = QComboBox()
        for name in output_devices:
            self.speakers.addItem(friendly_name(name), name)
        index = self.speakers.findData(current_speakers)
        self.speakers.setCurrentIndex(max(index, 0))
        form.addRow("You hear your student on", self.speakers)
        form.addRow("", label("The headphones or speakers your student's voice comes out of.", "hint"))

        self.quality = QComboBox()
        for text, model in QUALITY:
            self.quality.addItem(text, model)
        if self.quality.findData(cfg.llm_model) < 0:
            self.quality.addItem(f"Custom: {cfg.llm_model}", cfg.llm_model)
        self.quality.setCurrentIndex(self.quality.findData(cfg.llm_model))
        form.addRow("Feedback quality", self.quality)

        self.save_audio = QCheckBox("Keep a recording of each lesson (about 170 MB per 45 minutes)")
        self.save_audio.setChecked(cfg.save_audio)
        form.addRow("Lesson audio", self.save_audio)

        folder_row = QHBoxLayout()
        self.folder = QLineEdit(str(cfg.lessons_path))
        self.folder.setReadOnly(True)
        browse = QPushButton("Change...")
        browse.clicked.connect(self._browse)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        form.addRow("Save lessons in", folder_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(self, "Save lessons in", self.folder.text())
        if chosen:
            self.folder.setText(chosen)

    def _save(self):
        model = self.quality.currentData()
        self.model_changed = model != settings.get().llm_model
        settings.update(
            last_microphone=self.mic.currentText(),
            last_speakers=self.speakers.currentData() or "",
            llm_model=model,
            save_audio=self.save_audio.isChecked(),
            lessons_dir=self.folder.text(),
        )
        self.accept()
