import sounddevice as sd
import numpy as np
import torch

VADSAMPLERATE = 16000


def listen(
    vad_model,
    audio_device,
    sample_rate,
    silence_timeout_sec=2.5,
    max_turn_sec=1000,
    speech_threshold=0.5,
):

    frame_samples = 512
    frame_druation_sec = frame_samples / sample_rate
    needed_silence_frames = int(silence_timeout_sec / frame_druation_sec)
    max_frames = int(max_turn_sec / frame_druation_sec)

    captured = []
    silent_streak = 0
    started_speaking = False

    print("Listening...")
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=audio_device,
        blocksize=frame_samples,
    ) as stream:
        for _ in range(max_frames):
            frame, _ = stream.read(frame_samples)
            tensor = torch.from_numpy(frame.flatten())
            speech_prob = vad_model(tensor, sample_rate).item()
            is_speech = speech_prob > speech_threshold

            if is_speech:
                if not started_speaking:
                    print("Heard you, recording...")
                    started_speaking = True
                captured.append(frame)
                silent_streak = 0
            elif started_speaking:
                captured.append(frame)
                silent_streak += 1
                if silent_streak >= needed_silence_frames:
                    print("Got it.")
                    break

    if not captured:
        return np.array([], dtype=np.float32), sample_rate

    audio = np.concatenate(captured).astype(np.float32)
    return audio, sample_rate
