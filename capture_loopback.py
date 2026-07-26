import pyaudiowpatch as pyaudio   
import numpy as np
import torch
from scipy.signal import resample_poly
from math import gcd

VADSAMPLERATE = 16000


def find_loopback_device():
    with pyaudio.PyAudio() as p:
        wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        speakers = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
        if not speakers["isLoopbackDevice"]:
            for lb in p.get_loopback_device_info_generator():
                if speakers["name"] in lb["name"]:
                    return lb
        else:
            return speakers
    raise RuntimeError("No loopback device found")


def capture_loopback(vad_model, loopback_device, stop_flag):
    device_rate = int(loopback_device["defaultSampleRate"])   # 48000
    channels = loopback_device["maxInputChannels"]            # usually 2
    device_index = loopback_device["index"]

    # We want 512 samples PER VAD FRAME, but at 16k.
    # At 48k that means reading 1536 frames each time (1536 / 3 = 512).
    g = gcd(device_rate, VADSAMPLERATE)
    up, down = VADSAMPLERATE // g, device_rate // g          # 1, 3 at 48k
    read_frames = 512 * down // up                           # 1536 at 48k

    frame_duration_sec = 512 / VADSAMPLERATE
    needed_silence_frames = int(2.5 / frame_duration_sec)

    captured_segment = []
    silent_streak = 0
    is_talking = False

    print("Listening to loopback...")
    with pyaudio.PyAudio() as p:
        with p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=device_rate,
            frames_per_buffer=read_frames,
            input=True,
            input_device_index=device_index,
        ) as stream:
            try:
                while not stop_flag.is_set():
                    raw = stream.read(read_frames, exception_on_overflow=False)

                    # --- the three new bits ---
                    data = np.frombuffer(raw, dtype=np.int16)          # 1. int16
                    data = data.reshape(-1, channels).astype(np.float32)
                    mono = data.mean(axis=1) / 32768.0                 # 2. stereo->mono + float32
                    frame = resample_poly(mono, up, down).astype(np.float32)  # 3. 48k->16k -> 512 samples
                    # --------------------------

                    tensor = torch.from_numpy(frame)
                    is_speech = vad_model(tensor, VADSAMPLERATE).item() > 0.5
                    if is_speech:
                        captured_segment.append(frame)
                        silent_streak = 0
                        is_talking = True
                    elif is_talking:
                        captured_segment.append(frame)
                        silent_streak += 1
                        if silent_streak >= needed_silence_frames:
                            audio = np.concatenate(captured_segment)
                            yield audio, VADSAMPLERATE
                            captured_segment = []
                            silent_streak = 0
                            is_talking = False
            except KeyboardInterrupt:
                print("Loopback ended.")
