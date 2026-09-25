"""Tells the teacher when a newer Lesson Lens is out.

It's a plain request for the latest release's version number: no lesson data,
names or settings are sent.
"""
import logging

import requests

from . import REPO, __version__

log = logging.getLogger(__name__)


def _parse(version):
    try:
        return tuple(int(part) for part in version.lstrip("v").split(".")[:3])
    except ValueError:
        return ()


def newer_version():
    """The latest version number if it's newer than this one, else None. Never raises."""
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/releases/latest", timeout=5,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        latest = r.json()["tag_name"]
    except Exception as e:  # offline, rate-limited, no releases yet: just skip it
        log.info("Update check skipped: %s", e)
        return None
    if _parse(latest) > _parse(__version__):
        log.info("Version %s is available (this is %s)", latest, __version__)
        return latest.lstrip("v")
    return None
