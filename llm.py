"""Everything that talks to Ollama. Docs: https://docs.ollama.com/api/introduction"""
import json
import math

import requests
from pydantic import ValidationError

import config
from feedback_structure import StudentFeedback
from prompts import FEEDBACK_SYSTEM_PROMPT


class OllamaError(RuntimeError):
    """A problem with Ollama, worded so it can be shown to the user as-is."""


def _url(path):
    return config.OLLAMA_URL.rstrip("/") + path


def _full_name(model):
    # /api/tags reports "llama3.1:latest", so "llama3.1" has to be compared as that.
    return model if ":" in model else model + ":latest"


def check_ollama():
    """Return Ollama's version, or raise OllamaError if it isn't running."""
    try:
        r = requests.get(_url("/api/version"), timeout=5)
        r.raise_for_status()
        return r.json().get("version", "unknown")
    except requests.RequestException as e:
        raise OllamaError(
            "Ollama isn't running.\n\nOpen the Ollama app (or run 'ollama serve') and try again."
        ) from e


def ensure_model(on_progress=print):
    """Make sure Ollama is up and the model is downloaded. Pulls it if missing."""
    check_ollama()
    model = config.LLM_MODEL
    r = requests.get(_url("/api/tags"), timeout=10)
    r.raise_for_status()
    installed = {m["name"] for m in r.json().get("models", [])}
    if _full_name(model) in installed:
        return

    on_progress(f"Downloading AI model '{model}' (one-time, can take a while)...")
    last_pct = -1
    try:
        with requests.post(_url("/api/pull"), json={"model": model}, stream=True, timeout=(5, 120)) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if "error" in event:
                    raise OllamaError(f"Couldn't download '{model}': {event['error']}")
                total, done = event.get("total"), event.get("completed")
                if total and done:
                    pct = int(done * 100 / total)
                    if pct != last_pct:
                        on_progress(f"Downloading '{model}': {pct}%")
                        last_pct = pct
    except requests.RequestException as e:
        raise OllamaError(f"Download of '{model}' failed: {e}") from e


def _estimate_tokens(text):
    # Rough rule for English: ~3.5 characters per token. Good enough to size the context.
    return math.ceil(len(text) / 3.5)


def _pick_context(prompt_tokens):
    """Smallest power-of-two context that fits the prompt plus room for the answer."""
    needed = prompt_tokens + 3000
    ctx = config.MIN_CONTEXT
    while ctx < needed and ctx < config.MAX_CONTEXT:
        ctx *= 2
    return min(ctx, config.MAX_CONTEXT), needed


def generate_feedback(transcript, on_progress=print):
    """Send the transcript to Ollama and get back a validated StudentFeedback."""
    schema = StudentFeedback.model_json_schema()
    user_msg = (
        "Here is the lesson transcript:\n\n<transcript>\n"
        f"{transcript}\n</transcript>\n\n"
        f"Answer with JSON that matches this schema:\n{json.dumps(schema)}"
    )
    num_ctx, needed = _pick_context(_estimate_tokens(FEEDBACK_SYSTEM_PROMPT + user_msg))
    if needed > num_ctx:
        on_progress(
            f"Warning: this lesson (~{needed} tokens) is longer than MAX_CONTEXT ({num_ctx}). "
            "The start of it will be cut off. Raise MAX_CONTEXT in config.py if you have the memory."
        )

    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": FEEDBACK_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "format": schema,
        "stream": False,
        "options": {"temperature": config.LLM_TEMPERATURE, "num_ctx": num_ctx},
    }

    last_error = None
    for attempt in (1, 2):
        on_progress(f"Writing feedback with {config.LLM_MODEL} (attempt {attempt})...")
        try:
            r = requests.post(_url("/api/chat"), json=payload, timeout=(5, 900))
        except requests.Timeout as e:
            raise OllamaError("The AI took more than 15 minutes. Try a smaller model in config.py.") from e
        except requests.RequestException as e:
            raise OllamaError(f"Lost connection to Ollama: {e}") from e
        if r.status_code != 200:
            raise OllamaError(f"Ollama returned an error ({r.status_code}): {r.text[:300]}")

        data = r.json()
        try:
            return StudentFeedback.model_validate_json(data["message"]["content"])
        except (ValidationError, KeyError) as e:
            last_error = e
            payload["options"]["temperature"] = 0  # be stricter on the retry

    raise OllamaError(f"The AI's answer didn't match the feedback format twice.\n\n{last_error}")
