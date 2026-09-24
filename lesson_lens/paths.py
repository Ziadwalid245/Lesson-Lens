"""Where Lesson Lens keeps its files on this PC."""
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir, user_documents_dir, user_log_dir

APP_NAME = "Lesson Lens"

# appauthor=False, otherwise Windows gets "Lesson Lens\Lesson Lens".
CONFIG_DIR = Path(user_config_dir(APP_NAME, appauthor=False, roaming=True))  # %APPDATA%\Lesson Lens
DATA_DIR = Path(user_data_dir(APP_NAME, appauthor=False))                    # %LOCALAPPDATA%\Lesson Lens
LOG_DIR = Path(user_log_dir(APP_NAME, appauthor=False))                      # %LOCALAPPDATA%\Lesson Lens\Logs

SETTINGS_FILE = CONFIG_DIR / "settings.json"
# Kept out of Documents on purpose: OneDrive syncing a live SQLite file can corrupt it.
DB_FILE = DATA_DIR / "lesson_lens.db"
LOG_FILE = LOG_DIR / "lesson-lens.log"

# Transcripts, feedback and audio: somewhere the teacher can find them.
DEFAULT_LESSONS_DIR = Path(user_documents_dir()) / APP_NAME
