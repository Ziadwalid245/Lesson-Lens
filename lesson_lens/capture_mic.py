"""Teacher side: records the microphone with sounddevice."""
import time

import sounddevice as sd

from .vad import FRAME_SAMPLES, SAMPLE_RATE


def mic_frames(audio_device, stop_flag):
    """Yield (frame, arrived_at): 16 kHz mono float32 frames from the mic, until stop_flag is set."""
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=audio_device,
        extra_settings=sd.WasapiSettings(auto_convert=True),  # Windows does the 16 kHz mono conversion
        blocksize=FRAME_SAMPLES,
    ) as stream:
        while not stop_flag.is_set():
            frame, _overflowed = stream.read(FRAME_SAMPLES)
            yield frame.flatten(), time.monotonic()
