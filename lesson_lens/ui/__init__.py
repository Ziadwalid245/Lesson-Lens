"""The Lesson Lens window (PySide6)."""
import ctypes
import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .. import paths
from .main_window import MainWindow
from .style import STYLESHEET

log = logging.getLogger(__name__)


def run():
    # Its own taskbar icon and grouping, instead of Python's (matters when run from source).
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LessonLens.App")
    app = QApplication(sys.argv)
    app.setApplicationName("Lesson Lens")
    app.setWindowIcon(QIcon(str(Path(__file__).with_name("icon.png"))))
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)  # the design is light-only for now
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    logged_hook = sys.excepthook  # logs.setup() installed this

    def show_unexpected_error(exc_type, exc, tb):
        logged_hook(exc_type, exc, tb)
        QMessageBox.critical(None, "Lesson Lens",
                             f"Something went wrong: {exc}\n\nDetails are in the log:\n{paths.LOG_FILE}")

    sys.excepthook = show_unexpected_error  # Qt sends errors inside button clicks etc. here

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
