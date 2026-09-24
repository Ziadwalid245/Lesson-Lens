"""Saves each side of the lesson as a WAV file, so it can be re-transcribed later."""
import threading
import wave

import numpy as np

from .vad import SAMPLE_RATE

# Gaps longer than this are filled with silence. Shorter ones are just timing jitter.
_MAX_JITTER_SAMPLES = SAMPLE_RATE // 4


class WavRecorder:
    """Writes 16 kHz mono 16-bit audio to path, staying in step with the wall clock.

    WASAPI loopback delivers nothing at all while the PC is silent, so without
    padding student.wav would come out shorter than teacher.wav and the two
    would drift apart. Writing silence for those gaps keeps both files aligned
    with the transcript timestamps.

    Python's wave module rewrites the header after every write, so the file is
    still playable if the app crashes mid-lesson.
    """

    def __init__(self, path, t0):
        self._wav = wave.open(str(path), "wb")
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)
        self._wav.setframerate(SAMPLE_RATE)
        self._t0 = t0
        self._written = 0
        self._lock = threading.Lock()  # the loopback thread can outlive close() by a frame
        self._closed = False

    def tee(self, frames):
        """Pass (frame, arrived_at) pairs through unchanged, recording each one on the way."""
        for frame, arrived_at in frames:
            self.write(frame, arrived_at)
            yield frame, arrived_at

    def write(self, frame, arrived_at):
        with self._lock:
            if self._closed:
                return
            frame_start = round((arrived_at - self._t0) * SAMPLE_RATE) - len(frame)
            gap = frame_start - self._written
            if gap > _MAX_JITTER_SAMPLES:
                self._wav.writeframes(bytes(2 * gap))
                self._written += gap
            pcm = (np.clip(frame, -1.0, 1.0) * 32767).astype("<i2")
            self._wav.writeframes(pcm.tobytes())
            self._written += len(pcm)

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                self._wav.close()
