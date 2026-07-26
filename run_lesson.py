
from faster_whisper import WhisperModel
import numpy as np
from capture_loopback import capture_loopback, find_loopback_device
from capture_mic import listen
from scipy.signal import resample_poly
from math import gcd
import requests
import queue
import threading
from pathlib import Path
from datetime import datetime
from silero_vad import load_silero_vad
from feedback_structure import StudentFeedback, student_schema
from create_feedback import create_feedback_doc
WHISPERMODEL = "medium"
OLLAMA_URL = "http://localhost:11434/api/chat"
SENTINEL = object()





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

def queue_transcriber(transcript_path, model, audio_queue):
    with open(transcript_path, "a", encoding= "utf-8") as f: 
        while True: 
            audio_chunk = audio_queue.get()
            if audio_chunk is SENTINEL:
                break
            tag,audio,sr = audio_chunk
            text = transcribe(audio, sr, model)
            if text:   
                print(f" heard{tag}: {text}")
                f.write(f"{tag}: {text}" + "\n")
                f.flush()

def loopback_producer(vad_model, audio_queue, loopback_device,stop_flag):
       for audio, sr in capture_loopback(vad_model, loopback_device, stop_flag):
        audio_queue.put(("student", audio, sr))
  
def ask_ai(text):
    print("Responding")
    
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "student_feedback_assistant",
            "format": student_schema,
            "stream": False,
            "messages": [{"role": "user", "content": text}],
        },
    )
    response.raise_for_status()
    content = response.json()["message"]["content"] 
    feedback = StudentFeedback.model_validate_json(content)
    return feedback



def run_lesson(stop_flag, status_queue, input_device):
    Path("transcripts").mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    transcript_path = Path("transcripts") / f"lesson_{stamp}.txt"
    status_queue.put("Loading Whisper model...")
    model = WhisperModel(WHISPERMODEL, device="cpu", compute_type="int8")
    mic_vad = load_silero_vad()
    loop_vad = load_silero_vad()
    audio_queue = queue.Queue()
    consumer = threading.Thread(target=queue_transcriber, args=(transcript_path, model, audio_queue))
    consumer.start()
    loop_device = find_loopback_device()
    loopback_thread = threading.Thread(target=loopback_producer, args=(loop_vad, audio_queue, loop_device, stop_flag), daemon=True)
    loopback_thread.start()
    status_queue.put("Lesson started. Listening for audio...")
    try:
        for audio, sr in listen(mic_vad, audio_device=input_device, stop_flag=stop_flag):
            audio_queue.put(("teacher", audio, sr))
    finally:
        stop_flag.set()
        loopback_thread.join()
        audio_queue.put(SENTINEL)
        status_queue.put("Lesson ended. Processing transcript and generating feedback...")
        consumer.join()
    lesson = transcript_path.read_text(encoding="utf-8")
    feedback = ask_ai(lesson)
    create_feedback_doc(feedback, "student_feedback.docx")
    status_queue.put("Feedback generated and saved to student_feedback.docx")


if __name__ == "__main__":
    run_lesson(stop_flag=threading.Event(), status_queue=queue.Queue(), input_device=None)  # Replace with the desired input device index

