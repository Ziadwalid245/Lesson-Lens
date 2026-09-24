"""The lesson pipeline: record both sides -> transcribe -> AI feedback -> Word doc.

Talks to the window only through status_queue, using (kind, value) tuples:
  "started"  path of the new lesson folder   "line"   a new transcript line
  "level"    (speaker, loudness 0-1)          "info"   progress message
  "warning"  something the teacher should know; the lesson keeps going
  "error"    the run failed                   "done"   path of the lesson folder
"""
import logging
import queue
import re
import threading
import time
from datetime import datetime

import numpy as np
from silero_vad import load_silero_vad

from . import db, paths, settings
from .capture_loopback import loopback_frames
from .capture_mic import mic_frames
from .create_feedback import save_feedback
from .llm import OllamaError, ensure_model, generate_feedback
from .recording import WavRecorder
from .vad import phrases

log = logging.getLogger(__name__)

SENTINEL = object()


def fmt_time(seconds):
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def lesson_folder(root, started, student_name):
    """A new folder like '2026-09-24 15-30 Omar' that doesn't exist yet."""
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", student_name).strip().rstrip(".")
    base = started.strftime("%Y-%m-%d %H-%M") + (f" {safe_name}" if safe_name else "")
    folder, n = root / base, 2
    while folder.exists():
        folder, n = root / f"{base} ({n})", n + 1
    return folder


def loudness(frame):
    return float(np.sqrt(np.mean(frame * frame)))


def metered(speaker, frames, status):
    """Pass frames through, reporting how loud they are ~10 times a second for the level meters."""
    for i, (frame, arrived_at) in enumerate(frames):
        if i % 3 == 0:
            status.put(("level", (speaker, loudness(frame))))
        yield frame, arrived_at


def transcribe(audio, model, cfg):
    segments, _ = model.transcribe(
        audio,
        beam_size=5,
        language="en",
        initial_prompt=cfg.verbatim_prompt if cfg.verbatim_mode else None,
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcriber(model, cfg, audio_queue, lines, live_file, t0, status):
    """Consumer thread: turns audio chunks into (seconds, speaker, text) lines."""
    try:
        with open(live_file, "a", encoding="utf-8") as f:
            while True:
                item = audio_queue.get()
                if item is SENTINEL:
                    return
                speaker, audio, started_at = item
                try:
                    text = transcribe(audio, model, cfg)
                except Exception as e:  # one bad chunk must not kill the whole lesson
                    log.exception("Transcribing a %s phrase failed", speaker)
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
    except Exception as e:
        log.exception("The transcriber stopped")
        status.put(("warning", f"Live transcription stopped: {e}. The audio is still being recorded."))
        # Keep draining so the capture threads never block on a full queue.
        while audio_queue.get() is not SENTINEL:
            pass


def producer(speaker, frames, vad_model, cfg, audio_queue):
    for audio, started_at in phrases(frames, vad_model, cfg.vad_threshold, cfg.silence_seconds):
        audio_queue.put((speaker, audio, started_at))


def loopback_producer(frames, vad_model, cfg, audio_queue, status):
    try:
        producer("student", frames, vad_model, cfg, audio_queue)
    except Exception as e:
        log.exception("Student capture stopped")
        status.put(("warning", f"Your student's audio stopped recording ({e}). Only your side is being transcribed."))


def run_lesson(stop_flag, status, whisper_model, input_device, loopback_device, student_name=""):
    """Record one lesson until stop_flag is set, then write its feedback. whisper_model is loaded by the caller."""
    cfg = settings.get()
    lesson_dir = lesson_id = None
    try:
        # Check the AI BEFORE the lesson, not after 60 minutes of teaching.
        status.put(("info", "Checking the AI helper..."))
        ensure_model(lambda msg: status.put(("info", msg)))
        mic_vad, loop_vad = load_silero_vad(), load_silero_vad()

        started = datetime.now()
        lesson_dir = lesson_folder(cfg.lessons_path, started, student_name)
        lesson_dir.mkdir(parents=True)
        lesson_id = db.start_lesson(lesson_dir, started, student_name)
        log.info("Lesson %d started in %s (audio saved: %s)", lesson_id, lesson_dir, cfg.save_audio)
        status.put(("started", str(lesson_dir)))

        audio_queue, lines, recorders = queue.Queue(), [], []
        t0 = time.monotonic()
        teacher_frames = metered("teacher", mic_frames(input_device, stop_flag), status)
        student_frames = metered("student", loopback_frames(loopback_device, stop_flag), status)
        if cfg.save_audio:
            recorders = [WavRecorder(lesson_dir / "teacher.wav", t0), WavRecorder(lesson_dir / "student.wav", t0)]
            teacher_frames = recorders[0].tee(teacher_frames)
            student_frames = recorders[1].tee(student_frames)

        consumer = threading.Thread(
            target=transcriber, name="transcriber",
            args=(whisper_model, cfg, audio_queue, lines, lesson_dir / "transcript_live.txt", t0, status),
        )
        consumer.start()
        loopback_thread = threading.Thread(
            target=loopback_producer, name="student-capture",
            args=(student_frames, loop_vad, cfg, audio_queue, status),
            daemon=True,  # a loopback read can block while the PC is silent
        )
        loopback_thread.start()
        status.put(("info", "Recording"))

        try:
            producer("teacher", teacher_frames, mic_vad, cfg, audio_queue)
        except Exception as e:
            log.exception("Teacher capture stopped")
            status.put(("warning", f"Your microphone stopped recording ({e})."))
        finally:
            stop_flag.set()
            duration = time.monotonic() - t0
            loopback_thread.join(timeout=5)
            for recorder in recorders:
                recorder.close()
            status.put(("info", "Finishing the transcript..."))
            audio_queue.put(SENTINEL)
            consumer.join()
        log.info("Recording stopped after %.0f s, %d lines transcribed", duration, len(lines))

        if not lines:
            message = ("Nothing was transcribed, so there's no feedback to write.\n\n"
                       "Next time, press \"Check sound\" before the lesson to make sure both bars move.")
            db.set_status(lesson_id, "failed", message, duration_seconds=duration)
            status.put(("error", message))
            return

        # Lines arrive in the order they finished transcribing; sort by when they were spoken.
        lines.sort(key=lambda line: line[0])
        transcript = "\n".join(f"[{fmt_time(t)}] {spk}: {txt}" for t, spk, txt in lines)
        (lesson_dir / "transcript.txt").write_text(transcript, encoding="utf-8")
        db.set_status(lesson_id, "transcribed", duration_seconds=duration)

        status.put(("info", "Writing feedback..."))
        feedback = generate_feedback(transcript, lambda msg: None)
        save_feedback(feedback, lesson_dir, started.date())
        db.set_status(lesson_id, "done")
        log.info("Lesson %d done", lesson_id)
        status.put(("done", str(lesson_dir)))

    except OllamaError as e:
        log.warning("Ollama problem: %s", e)
        if lesson_id is None:  # failed the pre-lesson check: nothing was recorded
            status.put(("error", str(e)))
            return
        db.set_status(lesson_id, "failed", str(e))
        status.put(("error", f"{e}\n\nThe lesson is saved. Press \"Try again\" once the problem is fixed."))
    except Exception as e:
        log.exception("Lesson failed")
        if lesson_id is not None:
            db.set_status(lesson_id, "failed", f"{type(e).__name__}: {e}")
        status.put(("error", f"Something went wrong: {e}\n\nDetails are in the log:\n{paths.LOG_FILE}"))
