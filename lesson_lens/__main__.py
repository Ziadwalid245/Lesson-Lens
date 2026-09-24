"""Start Lesson Lens:  python -m lesson_lens              opens the window
                     python -m lesson_lens regenerate <transcript.txt>
"""
import argparse
import logging
import sys
from pathlib import Path

from . import __version__, db, logs, paths

log = logging.getLogger("lesson_lens")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lesson_lens", description="Lesson Lens: AI feedback for ESL lessons.")
    commands = parser.add_subparsers(dest="command")
    regen = commands.add_parser("regenerate", help="re-create feedback.docx from a saved transcript.txt")
    regen.add_argument("transcript", type=Path)
    args = parser.parse_args(argv)

    logs.setup()
    log.info("Lesson Lens %s starting (%s)", __version__, args.command or "gui")
    db.init()

    if args.command == "regenerate":
        from .regenerate import regenerate
        sys.exit(regenerate(args.transcript))

    db.mark_interrupted()
    log.info("Settings: %s | Data: %s", paths.SETTINGS_FILE, paths.DATA_DIR)
    from .gui import run
    run()


if __name__ == "__main__":
    main()
