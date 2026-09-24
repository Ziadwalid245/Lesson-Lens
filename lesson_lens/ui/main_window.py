"""The window: Getting ready -> Home -> Lesson -> Feedback."""
import logging

from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from .. import settings
from ..devices import choose, get_default_input_name, get_default_output_name, get_input_devices, get_output_devices
from .feedback_page import FeedbackPage
from .home_page import HomePage
from .lesson_page import LessonPage
from .settings_dialog import SettingsDialog
from .setup_page import SetupPage

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lesson Lens")
        self.resize(860, 760)
        self.whisper = None
        self.input_devices = get_input_devices()
        self.output_devices = get_output_devices()

        self.setup = SetupPage()
        self.home = HomePage(self.current_devices)
        self.lesson = LessonPage()
        self.feedback = FeedbackPage()
        self.stack = QStackedWidget()
        for page in (self.setup, self.home, self.lesson, self.feedback):
            self.stack.addWidget(page)
        self.setCentralWidget(self.stack)

        self.setup.ready.connect(self._ready)
        self.home.start_requested.connect(self._start_lesson)
        self.home.open_lesson.connect(self._open_feedback)
        self.home.settings_requested.connect(self._open_settings)
        self.lesson.feedback_ready.connect(self._open_feedback)
        self.lesson.back_home.connect(self._go_home)
        self.feedback.back_home.connect(self._go_home)

        self.stack.setCurrentWidget(self.setup)
        self.setup.start()

    def current_devices(self):
        """(mic name, mic index, speakers name, speakers info): last used, else the Windows default."""
        cfg = settings.get()
        mic = choose(cfg.last_microphone, self.input_devices, get_default_input_name())
        speakers = choose(cfg.last_speakers, self.output_devices, get_default_output_name())
        if mic is None:
            raise RuntimeError("No microphone found. Plug one in, then restart Lesson Lens.")
        if speakers is None:
            raise RuntimeError("No speakers or headphones found. Plug some in, then restart Lesson Lens.")
        return mic, self.input_devices[mic], speakers, self.output_devices[speakers]

    def _ready(self, whisper):
        self.whisper = whisper
        self._go_home()

    def _go_home(self):
        self.home.refresh()
        self.stack.setCurrentWidget(self.home)

    def _start_lesson(self, student):
        try:
            mic, mic_index, speakers, speakers_info = self.current_devices()
        except RuntimeError as e:
            QMessageBox.warning(self, "Lesson Lens", str(e))
            return
        settings.update(last_student=student, last_microphone=mic, last_speakers=speakers)
        self.stack.setCurrentWidget(self.lesson)
        self.lesson.start(self.whisper, mic_index, speakers_info, student)

    def _open_feedback(self, folder):
        self.stack.setCurrentWidget(self.feedback)
        self.feedback.show_lesson(folder)

    def _open_settings(self):
        self.home.stop_sound_check()
        self.output_devices = get_output_devices()  # pick up headphones plugged in since startup
        try:
            mic, _, speakers, _ = self.current_devices()
        except RuntimeError:
            mic = speakers = None
        dialog = SettingsDialog(self, self.input_devices, self.output_devices, mic, speakers)
        if dialog.exec() and dialog.model_changed:
            self.stack.setCurrentWidget(self.setup)
            self.setup.recheck_ai()  # downloads the new model if needed, then comes back home
        else:
            self.home.refresh_devices()

    def closeEvent(self, event):
        if self.lesson.is_running():
            answer = QMessageBox.warning(
                self, "Lesson Lens",
                "A lesson is still being recorded or turned into feedback.\n\n"
                "Quit anyway? The audio and transcript so far stay in the lesson folder.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            log.warning("Window closed during a lesson")
            self.lesson.stop_flag.set()
        self.home.stop_sound_check()
        event.accept()
