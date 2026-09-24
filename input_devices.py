import sounddevice as sd


def _wasapi_index():
    for i, api in enumerate(sd.query_hostapis()):
        if api["name"] == "Windows WASAPI":
            return i
    raise RuntimeError("WASAPI not found. Lesson Lens needs Windows.")


def get_input_devices():
    """{microphone name: sounddevice index} for WASAPI microphones."""
    wasapi = _wasapi_index()
    return {
        d["name"]: idx
        for idx, d in enumerate(sd.query_devices())
        if d["max_input_channels"] > 0 and d["hostapi"] == wasapi
    }


def get_default_input_name():
    """Name of the Windows default microphone, or None."""
    idx = sd.query_hostapis(_wasapi_index())["default_input_device"]
    return sd.query_devices(idx)["name"] if idx >= 0 else None
