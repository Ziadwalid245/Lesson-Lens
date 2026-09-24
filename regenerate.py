"""Re-create the feedback for a lesson from its saved transcript.

Use it when Ollama was off during the lesson, or to test prompt changes:
    python regenerate.py "C:\\Users\\you\\Documents\\Lesson Lens\\2026-09-24_15-30-00\\transcript.txt"
"""
import sys
from pathlib import Path

from create_feedback import create_feedback_doc
from llm import OllamaError, ensure_model, generate_feedback


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    transcript_path = Path(sys.argv[1])
    transcript = transcript_path.read_text(encoding="utf-8")
    try:
        ensure_model(print)
        feedback = generate_feedback(transcript, print)
    except OllamaError as e:
        print(f"\n{e}")
        sys.exit(1)
    out = transcript_path.with_name("feedback.docx")
    create_feedback_doc(feedback, out)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
