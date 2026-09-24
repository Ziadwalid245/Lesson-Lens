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

## Run from source

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m lesson_lens
```

If the AI step fails, nothing is lost: fix the problem, then run

```powershell
python -m lesson_lens regenerate "<lesson folder>\transcript.txt"
```

(With the .exe: `LessonFeedbackTool.exe regenerate "<lesson folder>\transcript.txt"`.)

## Where things are

| What | Where |
|---|---|
| Lessons: `transcript.txt`, `feedback.docx`, `teacher.wav`, `student.wav` | `Documents\Lesson Lens\<date_time>\` |
| Your settings | `%APPDATA%\Lesson Lens\settings.json` |
| Lesson database (students, lesson history) | `%LOCALAPPDATA%\Lesson Lens\lesson_lens.db` |
| Log file (for bug reports) | `%LOCALAPPDATA%\Lesson Lens\Logs\lesson-lens.log` |

**Settings.** The defaults and what each one does are in `lesson_lens/settings.py`. To change one, put just that key in `settings.json` and restart, e.g.

```json
{ "llm_model": "gemma4:e4b", "save_audio": false }
```

Keys you don't write keep following the defaults, so later updates still reach you. Prompts are in `lesson_lens/prompts.py`.

**Audio** is saved as 16 kHz WAV, about 85 MB per side for a 45-minute lesson. If your Documents folder syncs to OneDrive, that adds up: set `"save_audio": false` or point `"lessons_dir"` somewhere that isn't synced.

## Code map

| Module | Job |
|---|---|
| `gui.py` | The window |
| `pipeline.py` | One lesson: record → transcribe → feedback → Word |
| `capture_mic.py`, `capture_loopback.py` | Teacher and student audio (see below) |
| `vad.py` | Cuts audio into phrases with Silero VAD |
| `recording.py` | Saves each side to WAV |
| `llm.py`, `prompts.py`, `feedback_structure.py` | Ollama, the prompt, and the feedback format |
| `create_feedback.py` | The Word document |
| `db.py` | SQLite database of students and lessons |
| `settings.py`, `paths.py`, `logs.py` | Settings, file locations, logging |

## Design notes

**Why two audio libraries?**

The teacher's mic is captured with `sounddevice`. The student's audio is captured with `pyaudiowpatch`.

This looks redundant, but `sounddevice` cannot open a Windows loopback device — there's no API for it. On Linux this wouldn't be a problem: PulseAudio and PipeWire expose `.monitor` sources that behave like ordinary microphones, so one library would cover both. Windows has no equivalent, so capturing system output requires WASAPI loopback, and `pyaudiowpatch` is the only maintained option.

The cost is that `pyaudiowpatch` gives you the raw device stream — 48kHz stereo — so `lesson_lens/capture_loopback.py` has to convert to mono and resample down to the 16kHz that Whisper and the VAD expect. The `sounddevice` path gets this free via `auto_convert=True`.

**Don't consolidate these into one library.** Both sides share the phrase-cutting in `vad.py`, but rewriting the loopback capture with `sounddevice` doesn't raise an error — the loopback device simply won't appear in the device list, and the student's half of the lesson goes silently missing.