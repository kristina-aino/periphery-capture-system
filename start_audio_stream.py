import time
import logging
import argparse

from json import load

from device_capture_system.datamodel import AudioDevice
from device_capture_system.core import MultiInputStreamPublisher

# ---------------------------------------------------------------------

# AudioInputReader.list_devices()
ARGS = argparse.ArgumentParser()
ARGS.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = ARGS.parse_args()

# ---------------------------------------------------------------------

logging.basicConfig(level=ARGS.logging_level.upper())

# ---------------------------------------------------------------------

if __name__ == "__main__":
    
    with open("audio_device_configs.json", "r") as f:
        audio_device_configs = load(f)
    
    uuid = "Logitech StreamC - Microphone"
    audio_device = AudioDevice(uuid=uuid, **audio_device_configs[uuid])
    mcp = MultiInputStreamPublisher(devices=[audio_device])
    
    try:
        
        mcp.start()
        
        t = time.perf_counter()
        for i in range(100):
            time.sleep(0.01)
            
            
        print(f"fps: { 1 / (( time.perf_counter() - t ) / 100) }")
        
        
    except:
        raise
    finally:
        mcp.stop()