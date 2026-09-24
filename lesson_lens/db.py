"""The lesson database: which student each lesson was with and how it went.

The transcript, feedback and audio stay as files in the lesson folder; the
database only indexes them. Every function opens its own short connection, so
it's safe to call from the lesson thread and the GUI thread alike.
"""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from . import paths

# Append-only: never edit a migration that has shipped, add a new one instead.
MIGRATIONS = [
    """
    CREATE TABLE students (
        id          INTEGER PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
        notes       TEXT NOT NULL DEFAULT '',
        created_at  TEXT NOT NULL
    );
    CREATE TABLE lessons (
        id                INTEGER PRIMARY KEY,
        student_id        INTEGER REFERENCES students(id) ON DELETE SET NULL,
        started_at        TEXT NOT NULL,          -- local time, ISO 8601
        duration_seconds  REAL,
        folder            TEXT NOT NULL UNIQUE,
        status            TEXT NOT NULL CHECK (status IN ('recording', 'transcribed', 'done', 'failed')),
        error             TEXT
    );
    CREATE INDEX lessons_by_student ON lessons(student_id, started_at);
    """,
]


def _now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    con = sqlite3.connect(paths.DB_FILE, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init():
    """Create or upgrade the database. Call once at startup."""
    paths.DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as con:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version > len(MIGRATIONS):
            raise RuntimeError(
                f"{paths.DB_FILE} was made by a newer Lesson Lens. Update the app to open it."
            )
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            # One transaction per migration, so a failure leaves the old version intact.
            con.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")


def mark_interrupted():
    """Lessons still 'recording' at startup were cut short by a crash or power cut."""
    with closing(connect()) as con, con:
        con.execute(
            "UPDATE lessons SET status = 'failed', error = 'The app closed during the lesson.' "
            "WHERE status = 'recording'"
        )


def student_names():
    with closing(connect()) as con:
        return [row["name"] for row in con.execute("SELECT name FROM students ORDER BY name")]


def _student_id(con, name):
    con.execute(
        "INSERT INTO students (name, created_at) VALUES (?, ?) ON CONFLICT(name) DO NOTHING",
        (name, _now()),
    )
    return con.execute("SELECT id FROM students WHERE name = ?", (name,)).fetchone()["id"]


def start_lesson(folder, started_at, student_name=None):
    """Record a new lesson and return its id. A blank student name means 'not set'."""
    student_name = (student_name or "").strip()
    with closing(connect()) as con, con:
        student_id = _student_id(con, student_name) if student_name else None
        cur = con.execute(
            "INSERT INTO lessons (student_id, started_at, folder, status) VALUES (?, ?, ?, 'recording')",
            (student_id, started_at.isoformat(timespec="seconds"), str(Path(folder).resolve())),
        )
        return cur.lastrowid


def set_status(lesson_id, status, error=None, duration_seconds=None):
    with closing(connect()) as con, con:
        con.execute(
            "UPDATE lessons SET status = ?, error = ?, "
            "duration_seconds = COALESCE(?, duration_seconds) WHERE id = ?",
            (status, error, duration_seconds, lesson_id),
        )


def lesson_for_folder(folder):
    """The lesson row saved in this folder, or None if it isn't in the database."""
    with closing(connect()) as con:
        return con.execute(
            "SELECT * FROM lessons WHERE folder = ?", (str(Path(folder).resolve()),)
        ).fetchone()
