import sounddevice as sd
import silero_vad
from silero_vad import load_silero_vad
import torch
from faster_whisper import WhisperModel
import numpy as np
from get_audio import listen
from scipy.signal import resample_poly
from math import gcd
import requests

AUDIODEVICE = "soundcore Space One"
WHISPERMODEL = "medium"
OLLAMA_URL = "http://localhost:11434/api/chat"


def find_device(audio_device=AUDIODEVICE):
    audio_device = audio_device.lower()
    for idx, dev in enumerate(sd.query_devices()):
        found_devices = dev["name"].lower()
        if audio_device in found_devices and dev["max_input_channels"] > 1:
            sample_rate = int(dev["default_samplerate"])
            print(f"Matched device: {idx}: {dev['name']}")
            return idx, sample_rate
    raise RuntimeError(
        f"No input device matching all of {audio_device} found. "
        f"Run `python -c 'import sounddevice as sd; print(sd.query_devices())'` to see options."
    )


def transcribe(audio, sample_rate, model):
    print("Transcribing.....")
    if sample_rate != 16000:
        g = gcd(sample_rate, 16000)
        audio = resample_poly(audio, 16000 // g, sample_rate // g).astype(np.float32)
    segments, info = model.transcribe(audio=audio, beam_size=5, language="en")
    text = []
    for seg in segments:
        text.append(seg.text.strip())
    return " ".join(text)


def ask_ai(text):
    print("Responding")
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "test",
            "stream": False,
            "messages": [{"role": "user", "content": text}],
        },
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def main():
    print(f"Loading Whisper model '{WHISPERMODEL}'...")
    model = WhisperModel(WHISPERMODEL, device="cpu", compute_type="int8")
    vad_model = load_silero_vad()

    sample_rate, idx = find_device()
    print("Ready! \n")
    while True:
        audio, sample_rate = listen(
            vad_model, audio_device="default", sample_rate=16000
        )
        if len(audio) == 0:
            print("Nothing was heard. Listening again \n")
            continue
        text = transcribe(audio=audio, sample_rate=sample_rate, model=model)
        print(f" heard{text} ")
        reply = ask_ai(text)
        print(f"reply {reply}")


if __name__ == "__main__":
    main()
