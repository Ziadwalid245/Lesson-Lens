import sounddevice as sd
import numpy as np
import torch

VADSAMPLERATE = 16000


def listen(
    vad_model,
    audio_device,
    sample_rate,
):

    frame_samples = 512
    frame_duration_sec = frame_samples / sample_rate
    needed_silence_frames = int(2.5 / frame_duration_sec)

    captured_segment = []
    silent_streak = 0
    is_talking = False

    print("Listening...")
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=audio_device,
        blocksize=frame_samples,
    ) as stream:
        try:
            while True:
                frame, _ = stream.read(frame_samples)
                tensor = torch.from_numpy(frame.flatten())
                is_speech = vad_model(tensor, sample_rate).item() > 0.5
                if is_speech:
                    captured_segment.append(frame.flatten())
                    silent_streak = 0
                    is_talking = True
                elif is_talking:
                    captured_segment.append(frame.flatten())
                    silent_streak += 1
                    if silent_streak >= needed_silence_frames:
                        audio = np.concatenate(captured_segment)
                        yield audio, sample_rate
                        captured_segment = []
                        silent_streak = 0
                        is_talking = False
        except KeyboardInterrupt:
            print("Call ended.")
