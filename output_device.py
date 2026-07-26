import sounddevice as sd

def get_output_devices():
    output_devices = {}
    for idx, device in enumerate(sd.query_devices()):
        if device['max_output_channels'] > 0:
            api_name = sd.query_hostapis()[device['hostapi']]['name']
            if api_name == "Windows WASAPI":
                output_devices[device['name']] = idx
    return output_devices