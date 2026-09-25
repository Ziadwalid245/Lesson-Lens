# Lesson Lens

An AI tool that helps ESL teachers give more accurate, better structured feedback to their students.

It records both teacher and student, transcribes the lesson, and uses a local AI model to write up the feedback as a Word document.

Fully private — no audio, transcripts, or feedback ever leave your computer.

**Windows only** (for now)

## Download

[Download the latest release](https://github.com/Ziadwalid245/lesson-lens/releases/latest)

Unzip the folder and run `Lesson Lens.exe`. No Python needed. Windows may say "Windows protected your PC" because the app isn't code-signed yet: click **More info**, then **Run anyway**.

You'll also need [Ollama](https://ollama.com). If it's missing, the app tells you and links to the download; if it's installed but closed, the app starts it for you.

[Watch the demo ](https://youtu.be/zr9_7VPAwic)

## Using it

1. **Getting ready.** On start, the app checks the AI helper and loads the speech engine. The first time, it downloads them (about 11 GB in total).
2. **Home.** Type your student's name and press **Check sound**: say something, then play a video with talking. Both bars should move. Then press **Start lesson**.
3. **Lesson.** Teach as normal. The bars show that both sides are being heard. Press **End lesson** when you're done.
4. **Feedback.** After about a minute, the feedback appears. Edit anything you like, then **Save and open in Word** or **Copy for email or WhatsApp**.

Past lessons are listed on the home screen. If the feedback couldn't be written (for example, Ollama was closed), press **Try again** next to that lesson.

## Run from source

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m lesson_lens
```

If the AI step fails, nothing is lost: press **Try again** in the app, or run

```powershell
python -m lesson_lens regenerate "<lesson folder>\transcript.txt"
```

That command is also handy for testing prompt changes on a real lesson without teaching a new one.

## Where things are

| What | Where |
|---|---|
| Lessons: `transcript.txt`, `feedback.docx`, `feedback.json`, `teacher.wav`, `student.wav` | `Documents\Lesson Lens\<date time student>\` |
| Your settings | `%APPDATA%\Lesson Lens\settings.json` |
| Lesson database (students, lesson history) | `%LOCALAPPDATA%\Lesson Lens\lesson_lens.db` |
| Log file (for bug reports) | `%LOCALAPPDATA%\Lesson Lens\Logs\lesson-lens.log` |

**Settings.** The everyday ones (devices, feedback quality, lesson audio, lessons folder) are in the app's **Settings** window. Everything else, with what each one does, is in `lesson_lens/settings.py`. To change one, put just that key in `settings.json` and restart, e.g.

```json
{ "whisper_model": "medium.en", "silence_seconds": 2.0 }
```

**Feedback quality.** The default AI model is `gemma4:e4b`. On a test transcript it caught all three learner errors. `llama3.1` ("Faster" in Settings) took 21 s instead of 54 s, but it caught only one and praised a mistake as correct.

Keys you don't write keep following the defaults, so later updates still reach you. Prompts are in `lesson_lens/prompts.py`.

**Audio** is saved as 16 kHz WAV, about 85 MB per side for a 45-minute lesson. If your Documents folder syncs to OneDrive, that adds up: set `"save_audio": false` or point `"lessons_dir"` somewhere that isn't synced.

## Code map

| Module | Job |
|---|---|
| `ui/` | The window (PySide6): Getting ready → Home → Lesson → Feedback, plus Settings |
| `pipeline.py` | One lesson: record → transcribe → feedback → Word |
| `speech.py` | Loads Whisper once at startup, so Start is instant |
| `capture_mic.py`, `capture_loopback.py` | Teacher and student audio (see below) |
| `vad.py` | Cuts audio into phrases with Silero VAD |
| `recording.py` | Saves each side to WAV |
| `llm.py`, `prompts.py`, `feedback_structure.py` | Ollama, the prompt, and the feedback format |
| `create_feedback.py` | The Word document, `feedback.json`, and the email text |
| `db.py` | SQLite database of students and lessons |
| `settings.py`, `paths.py`, `logs.py` | Settings, file locations, logging |

## Design notes

**Why two audio libraries?**

The teacher's mic is captured with `sounddevice`. The student's audio is captured with `pyaudiowpatch`.

This looks redundant, but `sounddevice` cannot open a Windows loopback device — there's no API for it. On Linux this wouldn't be a problem: PulseAudio and PipeWire expose `.monitor` sources that behave like ordinary microphones, so one library would cover both. Windows has no equivalent, so capturing system output requires WASAPI loopback, and `pyaudiowpatch` is the only maintained option.

The cost is that `pyaudiowpatch` gives you the raw device stream — 48kHz stereo — so `lesson_lens/capture_loopback.py` has to convert to mono and resample down to the 16kHz that Whisper and the VAD expect. The `sounddevice` path gets this free via `auto_convert=True`.

**Don't consolidate these into one library.** Both sides share the phrase-cutting in `vad.py`, but rewriting the loopback capture with `sounddevice` doesn't raise an error — the loopback device simply won't appear in the device list, and the student's half of the lesson goes silently missing.