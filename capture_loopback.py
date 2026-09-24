"""Student side: records what the computer plays (WASAPI loopback).

Must stay on pyaudiowpatch -- see "Why two audio libraries?" in readme.md.
"""
import time
from math import gcd

import numpy as np
import pyaudiowpatch as pyaudio
import torch
from scipy.signal import resample_poly

import config

VAD_SAMPLE_RATE = 16000
FRAME_SAMPLES = 512


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


def capture_loopback(vad_model, loopback_device, stop_flag):
    """Yield (audio, sample_rate, started_at) for every phrase the student says."""
    device_rate = int(loopback_device["defaultSampleRate"])  # usually 48000
    channels = loopback_device["maxInputChannels"]           # usually 2

    # Read enough device frames to end up with exactly 512 samples at 16 kHz.
    g = gcd(device_rate, VAD_SAMPLE_RATE)
    up, down = VAD_SAMPLE_RATE // g, device_rate // g        # 1, 3 at 48 kHz
    read_frames = FRAME_SAMPLES * down // up                 # 1536 at 48 kHz

    frame_seconds = FRAME_SAMPLES / VAD_SAMPLE_RATE
    needed_silence_frames = int(config.SILENCE_SECONDS / frame_seconds)
    captured, silent_streak, is_talking, started_at = [], 0, False, 0.0

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
                frame = resample_poly(mono, up, down).astype(np.float32)

                is_speech = vad_model(torch.from_numpy(frame), VAD_SAMPLE_RATE).item() > config.VAD_THRESHOLD
                if is_speech:
                    if not is_talking:
                        started_at = time.monotonic()
                    captured.append(frame)
                    silent_streak, is_talking = 0, True
                elif is_talking:
                    captured.append(frame)
                    silent_streak += 1
                    if silent_streak >= needed_silence_frames:
                        yield np.concatenate(captured), VAD_SAMPLE_RATE, started_at
                        captured, silent_streak, is_talking = [], 0, False

    if captured:
        yield np.concatenate(captured), VAD_SAMPLE_RATE, started_at
