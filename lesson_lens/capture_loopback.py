"""Student side: records what the computer plays (WASAPI loopback).

Must stay on pyaudiowpatch -- see "Why two audio libraries?" in readme.md.
"""
import time
from math import gcd

import numpy as np
import pyaudiowpatch as pyaudio
from scipy.signal import resample_poly

from .vad import FRAME_SAMPLES, SAMPLE_RATE


def find_loopback_device():
    """Loopback device for the current default speakers/headphones."""
    with pyaudio.PyAudio() as p:
        wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        speakers = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
        if speakers["isLoopbackDevice"]:
            return speakers
        for lb in p.get_loopback_device_info_generator():
            if speakers["name"] in lb["name"]:
                return lb
    raise RuntimeError("No loopback device found for your default speakers.")


def loopback_frames(loopback_device, stop_flag):
    """Yield (frame, arrived_at): 16 kHz mono float32 frames of what the PC plays, until stop_flag is set.

    The device gives raw 48 kHz stereo (usually), so this does by hand what
    sounddevice's auto_convert does for the mic.
    """
    device_rate = int(loopback_device["defaultSampleRate"])  # usually 48000
    channels = loopback_device["maxInputChannels"]           # usually 2

    # Read enough device frames to end up with exactly 512 samples at 16 kHz.
    g = gcd(device_rate, SAMPLE_RATE)
    up, down = SAMPLE_RATE // g, device_rate // g            # 1, 3 at 48 kHz
    read_frames = FRAME_SAMPLES * down // up                 # 1536 at 48 kHz

    with pyaudio.PyAudio() as p:
        with p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=device_rate,
            frames_per_buffer=read_frames,
            input=True,
            input_device_index=loopback_device["index"],
        ) as stream:
            while not stop_flag.is_set():
                raw = stream.read(read_frames, exception_on_overflow=False)
                data = np.frombuffer(raw, dtype=np.int16).reshape(-1, channels).astype(np.float32)
                mono = data.mean(axis=1) / 32768.0
                yield resample_poly(mono, up, down).astype(np.float32), time.monotonic()
