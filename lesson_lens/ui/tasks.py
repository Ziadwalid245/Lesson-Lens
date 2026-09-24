"""Run slow work (Ollama, Whisper, audio) off the UI thread and get the results back on it."""
import logging
import threading

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

_alive = set()  # relays must outlive their thread, or Qt drops the signals


class _Relay(QObject):
    progress = Signal(object)
    done = Signal(object)
    failed = Signal(object)


def run_task(fn, *, on_done=None, on_error=None, on_progress=None, name="task"):
    """Call fn(report) in a background thread.

    report(x) delivers x to on_progress on the UI thread. fn's return value goes
    to on_done, or its exception to on_error, also on the UI thread.
    """
    relay = _Relay()
    _alive.add(relay)
    if on_progress:
        relay.progress.connect(on_progress)
    if on_done:
        relay.done.connect(on_done)
    if on_error:
        relay.failed.connect(on_error)
    relay.done.connect(lambda _: _alive.discard(relay))
    relay.failed.connect(lambda _: _alive.discard(relay))

    def work():
        try:
            result = fn(relay.progress.emit)
        except Exception as e:
            log.warning("%s failed: %s", name, e, exc_info=True)
            relay.failed.emit(e)
        else:
            relay.done.emit(result)

    threading.Thread(target=work, name=name, daemon=True).start()
