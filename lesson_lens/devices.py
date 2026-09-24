"""The device lists for the two dropdowns.

Microphones come from sounddevice, speakers from pyaudiowpatch -- the same
libraries that record them, so whatever the teacher picks is exactly the
device that gets recorded. See "Why two audio libraries?" in readme.md.
"""
import pyaudiowpatch as pyaudio
import sounddevice as sd

from .capture_loopback import find_loopback_device


def _wasapi_index():
    for i, api in enumerate(sd.query_hostapis()):
        if api["name"] == "Windows WASAPI":
            return i
    raise RuntimeError("WASAPI not found. Lesson Lens needs Windows.")


def get_input_devices():
    """{microphone name: sounddevice index} for WASAPI microphones."""
    wasapi = _wasapi_index()
    return {
        d["name"]: idx
        for idx, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0 and d["hostapi"] == wasapi
    }


def get_default_input_name():
    """Name of the Windows default microphone, or None."""
    idx = sd.query_hostapis(_wasapi_index())["default_input_device"]
    return sd.query_devices(idx)["name"] if idx >= 0 else None


def get_output_devices():
    """{speakers name: pyaudiowpatch loopback device info}."""
    with pyaudio.PyAudio() as p:
        return {lb["name"]: lb for lb in p.get_loopback_device_info_generator()}


def get_default_output_name():
    try:
        return find_loopback_device()["name"]
    except RuntimeError:
        return None
