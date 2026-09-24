"""The lesson pipeline: record both sides -> transcribe -> AI feedback -> Word doc.

Talks to the GUI only through status_queue, using (kind, text) tuples:
  "info"    progress message          "line"  a new transcript line
  "warning" something the teacher should know, lesson keeps going
  "error"   the run failed               "done"  text = path of the lesson folder
"""
import logging
import queue
import threading
import time
from datetime import datetime

from faster_whisper import WhisperModel
from silero_vad import load_silero_vad

from . import db, paths, settings
from .capture_loopback import loopback_frames
from .capture_mic import mic_frames
from .create_feedback import create_feedback_doc
from .llm import OllamaError, ensure_model, generate_feedback
from .recording import WavRecorder
from .regenerate import regenerate_command
from .vad import phrases

log = logging.getLogger(__name__)

SENTINEL = object()
FOLDER_FORMAT = "%Y-%m-%d_%H-%M-%S"


def fmt_time(seconds):
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


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
        status.put(("warning", f"Live transcription stopped: {e}\n\nThe audio is still being recorded."))
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
        status.put(("warning", f"Student audio stopped recording: {e}\n\nOnly your side will be transcribed."))


def run_lesson(stop_flag, status, input_device, loopback_device, student_name=""):
    cfg = settings.get()
    lesson_dir = lesson_id = None
    try:
        # Check everything BEFORE the lesson, not after 60 minutes of teaching.
        status.put(("info", "Checking Ollama..."))
        ensure_model(lambda msg: status.put(("info", msg)))

        status.put(("info", f"Loading Whisper '{cfg.whisper_model}' (first run downloads it)..."))
        model = WhisperModel(cfg.whisper_model, device="cpu", compute_type="int8")
        mic_vad, loop_vad = load_silero_vad(), load_silero_vad()

        started = datetime.now()
        lesson_dir = cfg.lessons_path / started.strftime(FOLDER_FORMAT)
        lesson_dir.mkdir(parents=True, exist_ok=True)
        lesson_id = db.start_lesson(lesson_dir, started, student_name)
        log.info("Lesson %d started in %s (audio saved: %s)", lesson_id, lesson_dir, cfg.save_audio)

        audio_queue, lines, recorders = queue.Queue(), [], []
        t0 = time.monotonic()
        teacher_frames = mic_frames(input_device, stop_flag)
        student_frames = loopback_frames(loopback_device, stop_flag)
        if cfg.save_audio:
            recorders = [WavRecorder(lesson_dir / "teacher.wav", t0), WavRecorder(lesson_dir / "student.wav", t0)]
            teacher_frames = recorders[0].tee(teacher_frames)
            student_frames = recorders[1].tee(student_frames)

        consumer = threading.Thread(
            target=transcriber, name="transcriber",
            args=(model, cfg, audio_queue, lines, lesson_dir / "transcript_live.txt", t0, status),
        )
        consumer.start()
        loopback_thread = threading.Thread(
            target=loopback_producer, name="student-capture",
            args=(student_frames, loop_vad, cfg, audio_queue, status),
            daemon=True,  # a loopback read can block while the PC is silent
        )
        loopback_thread.start()
        status.put(("info", "Recording. Teach as normal, then press Stop."))

        try:
            producer("teacher", teacher_frames, mic_vad, cfg, audio_queue)
        except Exception as e:
            log.exception("Teacher capture stopped")
            status.put(("warning", f"Microphone stopped recording: {e}"))
        finally:
            stop_flag.set()
            duration = time.monotonic() - t0
            loopback_thread.join(timeout=5)
            for recorder in recorders:
                recorder.close()
            status.put(("info", "Finishing the transcript (can take a minute)..."))
            audio_queue.put(SENTINEL)
            consumer.join()
        log.info("Recording stopped after %.0f s, %d lines transcribed", duration, len(lines))

        if not lines:
            message = "Nothing was transcribed. Check that the right microphone and speakers are selected."
            db.set_status(lesson_id, "failed", message, duration_seconds=duration)
            status.put(("error", message))
            return

        # Lines arrive in the order they finished transcribing; sort by when they were spoken.
        lines.sort(key=lambda line: line[0])
        transcript = "\n".join(f"[{fmt_time(t)}] {spk}: {txt}" for t, spk, txt in lines)
        transcript_path = lesson_dir / "transcript.txt"
        transcript_path.write_text(transcript, encoding="utf-8")
        db.set_status(lesson_id, "transcribed", duration_seconds=duration)

        feedback = generate_feedback(transcript, lambda msg: status.put(("info", msg)))
        create_feedback_doc(feedback, lesson_dir / "feedback.docx", started.date())
        db.set_status(lesson_id, "done")
        log.info("Lesson %d done", lesson_id)
        status.put(("done", str(lesson_dir)))

    except OllamaError as e:
        log.warning("Ollama problem: %s", e)
        if lesson_id is None:  # failed the pre-lesson check: nothing was recorded
            status.put(("error", str(e)))
            return
        db.set_status(lesson_id, "failed", str(e))
        status.put(("error", f"{e}\n\nThe transcript is saved in:\n{lesson_dir}\n\n"
                             f"Once fixed, run:\n{regenerate_command(lesson_dir / 'transcript.txt')}"))
    except Exception as e:
        log.exception("Lesson failed")
        if lesson_id is not None:
            db.set_status(lesson_id, "failed", f"{type(e).__name__}: {e}")
        status.put(("error", f"Something went wrong: {e}\n\nDetails are in the log:\n{paths.LOG_FILE}"))
