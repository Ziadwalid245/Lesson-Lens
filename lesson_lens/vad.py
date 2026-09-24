"""Cuts a stream of audio frames into spoken phrases using Silero VAD.

Both capture modules produce the same kind of stream: (frame, time) pairs,
where frame is 512 float32 samples at 16 kHz and time is time.monotonic()
when it arrived. That's what Silero VAD needs, and what Whisper wants.
"""
import numpy as np
import torch

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512  # Silero VAD wants exactly 512 samples per frame at 16 kHz
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE


def phrases(frames, vad_model, threshold, silence_seconds):
    """Yield (audio, started_at) for every phrase, where a phrase ends after silence_seconds of quiet.

    started_at is time.monotonic() at the start of the phrase, so teacher and
    student lines can be put back in the right order afterwards.
    """
    needed_silence_frames = int(silence_seconds / FRAME_SECONDS)
    captured, silent_streak, started_at = [], 0, 0.0

    for frame, arrived_at in frames:
        is_speech = vad_model(torch.from_numpy(frame), SAMPLE_RATE).item() > threshold
        if is_speech:
            if not captured:
                started_at = arrived_at - FRAME_SECONDS
            captured.append(frame)
            silent_streak = 0
        elif captured:
            captured.append(frame)
            silent_streak += 1
            if silent_streak >= needed_silence_frames:
                yield np.concatenate(captured), started_at
                captured, silent_streak = [], 0

    if captured:  # still mid-sentence when Stop was pressed: keep it
        yield np.concatenate(captured), started_at
