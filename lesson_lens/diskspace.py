"""Checks there's room for the one-time downloads before starting them."""
import shutil
from pathlib import Path


class NotEnoughSpace(RuntimeError):
    """Worded so it can be shown to the teacher as-is."""


def require_free(folder, needed_gb, what):
    """Raise NotEnoughSpace unless the drive holding folder has needed_gb free."""
    probe = Path(folder)
    while not probe.exists() and probe != probe.parent:  # the folder may not exist yet
        probe = probe.parent
    free_gb = shutil.disk_usage(probe).free / 1e9
    if free_gb < needed_gb:
        raise NotEnoughSpace(
            f"There isn't enough free space to download {what}.\n\n"
            f"It needs about {needed_gb:.0f} GB on drive {probe.anchor}, and there's {free_gb:.1f} GB free.\n\n"
            "Delete some files or empty the Recycle Bin, then press \"Try again\"."
        )
