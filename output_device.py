"""Lists the speakers/headphones we can record the student from.

These come straight from pyaudiowpatch (not sounddevice), so whatever the
teacher picks in the dropdown is exactly the device that gets recorded.
"""
import pyaudiowpatch as pyaudio

from capture_loopback import find_loopback_device


def get_output_devices():
    """{device name: pyaudiowpatch loopback device info}."""
    with pyaudio.PyAudio() as p:
        return {lb["name"]: lb for lb in p.get_loopback_device_info_generator()}


def get_default_output_name():
    try:
        return find_loopback_device()["name"]
    except RuntimeError:
        return None
