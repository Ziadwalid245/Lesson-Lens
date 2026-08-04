# Lesson Lens

An AI tool that helps ESL teachers give more accurate, better structured feedback to their students.

It records both teacher and student, transcribes the lesson, and uses a local AI model to write up the feedback as a Word document.

Fully private — no audio, transcripts, or feedback ever leave your computer.

**Windows only** (for now)

## Download

[Download the latest release](https://github.com/Ziadwalid245/lesson-lens/releases/latest)

Unzip the folder and run `LessonFeedbackTool.exe`. No Python needed.

You'll also need [Ollama](https://ollama.com) installed and running.

[Watch the demo ](https://youtu.be/zr9_7VPAwic)

## Design notes

**Why two audio libraries?**

The teacher's mic is captured with `sounddevice`. The student's audio is captured with `pyaudiowpatch`.

This looks redundant, but `sounddevice` cannot open a Windows loopback device — there's no API for it. On Linux this wouldn't be a problem: PulseAudio and PipeWire expose `.monitor` sources that behave like ordinary microphones, so one library would cover both. Windows has no equivalent, so capturing system output requires WASAPI loopback, and `pyaudiowpatch` is the only maintained option.

The cost is that `pyaudiowpatch` gives you the raw device stream — 48kHz stereo — so `capture_loopback.py` has to convert to mono and resample down to the 16kHz that Whisper and the VAD expect. The `sounddevice` path gets this free via `auto_convert=True`.

**Don't consolidate these into one library.** Rewriting the loopback path with `sounddevice` doesn't raise an error — the loopback device simply won't appear in the device list, and the student's half of the lesson goes silently missing.