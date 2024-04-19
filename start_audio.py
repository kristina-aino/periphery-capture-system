import time
import pyaudio
from json import load

from camera_capture_system.datamodel import AudioDevice
from camera_capture_system.deviceIO import AudioInputReader

try:
    
    # AudioInputReader.list_devices()
    
    with open("audio_device_configs.json", "r") as f:
        audio_device_configs = load(f)
    
    uuid = "Logitech StreamC - Microphone"
    
    audio_device = AudioDevice(uuid=uuid, **audio_device_configs[uuid])
    
    print(audio_device)
    print(pyaudio.PyAudio().get_device_info_by_index(audio_device.id))
    
    air = AudioInputReader(audio_device)
    
    air.start()
    
    t = time.perf_counter()
    for i in range(100):
        print(air.read())
    print(f"fps: { 1 / (( time.perf_counter() - t ) / 100) }")
    
    
except:
    raise