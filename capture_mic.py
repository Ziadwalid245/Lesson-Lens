import sounddevice as sd
import numpy as np
import torch

VADSAMPLERATE = 16000


def listen(
    vad_model,
    audio_device,
    stop_flag,
    sample_rate=VADSAMPLERATE,
):

    frame_samples = 512
    frame_duration_sec = frame_samples / VADSAMPLERATE
    needed_silence_frames = int(2.5 / frame_duration_sec)

    captured_segment = []
    silent_streak = 0
    is_talking = False

    print("Listening...")
    with sd.InputStream(
        samplerate=VADSAMPLERATE,
        channels=1,
        dtype="float32",
        device=audio_device,
        extra_settings=sd.WasapiSettings(auto_convert=True),
        blocksize=frame_samples,
    ) as stream:
        while not stop_flag.is_set():
                    frame, _ = stream.read(frame_samples)
                    tensor = torch.from_numpy(frame.flatten())
                    is_speech = vad_model(tensor, VADSAMPLERATE).item() > 0.5
                    if is_speech:
                        captured_segment.append(frame.flatten())
                        silent_streak = 0
                        is_talking = True
                    elif is_talking:
                        captured_segment.append(frame.flatten())
                        silent_streak += 1
                        if silent_streak >= needed_silence_frames:
                            audio = np.concatenate(captured_segment)
                            yield audio, VADSAMPLERATE
                            captured_segment = []
                            silent_streak = 0
                            is_talking = False
