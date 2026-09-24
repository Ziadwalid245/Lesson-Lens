"""Teacher side: records the microphone and yields one chunk per spoken phrase."""
import time

import numpy as np
import sounddevice as sd
import torch

import config

VAD_SAMPLE_RATE = 16000
FRAME_SAMPLES = 512  # Silero VAD wants exactly 512 samples per frame at 16 kHz


def listen(vad_model, audio_device, stop_flag):
    """Yield (audio, sample_rate, started_at) for every phrase the teacher says.

    started_at is time.monotonic() at the start of the phrase, so teacher and
    student lines can be put back in the right order afterwards.
    """
    frame_seconds = FRAME_SAMPLES / VAD_SAMPLE_RATE
    needed_silence_frames = int(config.SILENCE_SECONDS / frame_seconds)

    captured, silent_streak, is_talking, started_at = [], 0, False, 0.0

    with sd.InputStream(
        samplerate=VAD_SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=audio_device,
        extra_settings=sd.WasapiSettings(auto_convert=True),
        blocksize=FRAME_SAMPLES,
    ) as stream:
        while not stop_flag.is_set():
            frame, _ = stream.read(FRAME_SAMPLES)
            frame = frame.flatten()
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

    if captured:  # teacher was mid-sentence when Stop was pressed: keep it
        yield np.concatenate(captured), VAD_SAMPLE_RATE, started_at
