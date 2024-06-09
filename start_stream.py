import time
import argparse

from logging import getLogger, basicConfig
from traceback import format_exc

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("--config", type=str, default="./configs/devices.json", help="path to device config file")
AP.add_argument("--ports", type=int, nargs="+", default=[10000, 10001, 10002], help="ports to stream video")
AP.add_argument("--host", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

basicConfig(level=ARGS.logging_level.upper())
logger = getLogger(__name__)

# ---------------------------------------------------------------------

# Setp 1: read camera configurations for all cameras
from periphery_capture_system.core import MultiInputStreamSender, MultiInputStreamReceiver
from periphery_capture_system.deviceIO import load_all_devices_from_config


if __name__ == "__main__":
    
    cameras = load_all_devices_from_config("video", config_file=ARGS.config)
    
    for cam in cameras:
        print(cam)
    
    multi_sender = MultiInputStreamSender(
        devices = cameras, 
        ports = ARGS.ports, 
        host = ARGS.host
    )
    multi_receiver = MultiInputStreamReceiver(
        ports = ARGS.ports,
        host = ARGS.host
    )
    
    try:
        multi_sender.start_processes()
        multi_receiver.start()
        
        time_taken = 0
        collected_frames = 0
        while collected_frames < 60:
            dt = time.time()
            frames = multi_receiver.read()
            if frames is None:
                continue
            time_taken += time.time() - dt
            collected_frames += 1
            print(f"collected {collected_frames} frames")
        print(f"fps: {60 / time_taken}")
        
        
    except Exception as e:
        raise e
    finally:
        multi_sender.stop_processes()
        multi_receiver.stop()