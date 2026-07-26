import sounddevice as sd

def get_input_devices():
    mic_devices = {}
    for idx, device in enumerate(sd.query_devices()):
      if device['max_input_channels'] > 0:
        api_name = sd.query_hostapis()[device['hostapi']]['name']
        if api_name == "Windows WASAPI":
         mic_devices[device['name']] = idx
    return mic_devices



