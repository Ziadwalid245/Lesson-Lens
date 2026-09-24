"""The lesson pipeline: record both sides -> transcribe -> AI feedback -> Word doc.

Talks to the GUI only through status_queue, using (kind, text) tuples:
  "info"    progress message          "line"  a new transcript line
  "warning" something the teacher should know, lesson keeps going
  "error"   the run failed               "done"  text = path of the lesson folder
"""
import queue
import threading
import time
import traceback
from datetime import datetime
from math import gcd

import numpy as np
from faster_whisper import WhisperModel
from scipy.signal import resample_poly
from silero_vad import load_silero_vad

import config
from capture_loopback import capture_loopback
from capture_mic import listen
from create_feedback import create_feedback_doc
from llm import OllamaError, ensure_model, generate_feedback

SENTINEL = object()


def fmt_time(seconds):
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def transcribe(audio, sample_rate, model):
    if sample_rate != 16000:
        g = gcd(sample_rate, 16000)
        audio = resample_poly(audio, 16000 // g, sample_rate // g).astype(np.float32)
    segments, _ = model.transcribe(
        audio,
        beam_size=5,
        language="en",
        initial_prompt=config.VERBATIM_PROMPT if config.VERBATIM_MODE else None,
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcriber(model, audio_queue, lines, live_file, t0, status):
    """Consumer thread: turns audio chunks into (seconds, speaker, text) lines."""
    with open(live_file, "a", encoding="utf-8") as f:
        while True:
            item = audio_queue.get()
            if item is SENTINEL:
                return
            speaker, audio, sr, started_at = item
            try:
                text = transcribe(audio, sr, model)
            except Exception as e:  # one bad chunk must not kill the whole lesson
                status.put(("warning", f"Skipped a {speaker} phrase that failed to transcribe: {e}"))
                continue
            if not text:
                continue
            offset = max(0.0, started_at - t0)
            lines.append((offset, speaker, text))
            line = f"[{fmt_time(offset)}] {speaker}: {text}"
            f.write(line + "\n")
            f.flush()
            status.put(("line", line))


def loopback_producer(vad, device, stop_flag, audio_queue, status):
    try:
        for audio, sr, started_at in capture_loopback(vad, device, stop_flag):
            audio_queue.put(("student", audio, sr, started_at))
    except Exception as e:
        status.put(("warning", f"Student audio stopped recording: {e}\n\nOnly your side will be transcribed."))


def run_lesson(stop_flag, status, input_device, loopback_device):
    lesson_dir = config.LESSONS_DIR / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    try:
        lesson_dir.mkdir(parents=True, exist_ok=True)

        # Check the AI BEFORE the lesson, not after 60 minutes of teaching.
        status.put(("info", "Checking Ollama..."))
        ensure_model(lambda msg: status.put(("info", msg)))

        status.put(("info", f"Loading Whisper '{config.WHISPER_MODEL}' (first run downloads it)..."))
        model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
        mic_vad, loop_vad = load_silero_vad(), load_silero_vad()

        audio_queue, lines = queue.Queue(), []
        t0 = time.monotonic()
        consumer = threading.Thread(
            target=transcriber,
            args=(model, audio_queue, lines, lesson_dir / "transcript_live.txt", t0, status),
        )
        consumer.start()
        loopback_thread = threading.Thread(
            target=loopback_producer,
            args=(loop_vad, loopback_device, stop_flag, audio_queue, status),
            daemon=True,
        )
        loopback_thread.start()
        status.put(("info", "Recording. Teach as normal, then press Stop."))

        try:
            for audio, sr, started_at in listen(mic_vad, input_device, stop_flag):
                audio_queue.put(("teacher", audio, sr, started_at))
        except Exception as e:
            status.put(("warning", f"Microphone stopped recording: {e}"))
        finally:
            stop_flag.set()
            loopback_thread.join(timeout=5)
            status.put(("info", "Finishing the transcript (can take a minute)..."))
            audio_queue.put(SENTINEL)
            consumer.join()

        if not lines:
            status.put(("error", "Nothing was transcribed. Check that the right microphone and speakers are selected."))
            return

        # Lines arrive in the order they finished transcribing; sort by when they were spoken.
        lines.sort(key=lambda line: line[0])
        transcript = "\n".join(f"[{fmt_time(t)}] {spk}: {txt}" for t, spk, txt in lines)
        transcript_path = lesson_dir / "transcript.txt"
        transcript_path.write_text(transcript, encoding="utf-8")

        feedback = generate_feedback(transcript, lambda msg: status.put(("info", msg)))
        create_feedback_doc(feedback, lesson_dir / "feedback.docx")
        status.put(("done", str(lesson_dir)))

    except OllamaError as e:
        status.put(("error", f"{e}\n\nAnything recorded is saved in:\n{lesson_dir}\n\n"
                             "Once fixed, run:  python regenerate.py <that folder>\\transcript.txt"))
    except Exception:
        (lesson_dir / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        status.put(("error", f"Something went wrong. Details saved to:\n{lesson_dir / 'error.log'}"))


if __name__ == "__main__":
    from capture_loopback import find_loopback_device

    q = queue.Queue()
    flag = threading.Event()
    threading.Timer(30, flag.set).start()  # 30-second smoke test
    run_lesson(flag, q, input_device=None, loopback_device=find_loopback_device())
    while not q.empty():
        print(q.get())
