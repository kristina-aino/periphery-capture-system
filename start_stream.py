import time
import argparse

from logging import getLogger, basicConfig
from traceback import format_exc

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("--config", type=str, default="./configs/devices.json", help="path to device config file")
AP.add_argument("--proxy_sub_port", type=int, default=10000, help="port for proxy subscriber")
AP.add_argument("--proxy_pub_port", type=int, default=10001, help="port for proxy publisher")
AP.add_argument("--host", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

basicConfig(level=ARGS.logging_level.upper())
logger = getLogger(__name__)

# ---------------------------------------------------------------------

# Setp 1: read camera configurations for all cameras
from device_capture_system.core import MultiInputStreamSender, InputStreamReceiver
from device_capture_system.deviceIO import load_all_devices_from_config
from device_capture_system.zmqIO import ZMQProxy


if __name__ == "__main__":
    
    cameras = load_all_devices_from_config("video", config_file=ARGS.config)
    
    for cam in cameras:
        print(cam)
    
    multi_sender = MultiInputStreamSender(
        devices = cameras, 
        proxy_sub_port=ARGS.proxy_sub_port, 
        host = ARGS.host
    )
    
    proxy = ZMQProxy(ARGS.host, ARGS.proxy_pub_port, ARGS.proxy_sub_port)
    
    receiver = InputStreamReceiver(
        proxy_pub_port=ARGS.proxy_pub_port,
        host = ARGS.host
    )
    
    try:
        
        proxy.start_process()
        multi_sender.start_processes()
        receiver.start()
        
        time_taken = 0
        collected_frames = 0
        while collected_frames < 180 * 10:
            dt = time.time()
            frame = receiver.read()
            if frame is None:
                continue
            time_taken += time.time() - dt
            collected_frames += 1
            print(f"collected {collected_frames} frames")
        print(f"fps: {180 * 10 / time_taken}")
        
        
    except Exception as e:
        raise e
    finally:
        multi_sender.stop_processes()
        proxy.stop_process()
        receiver.stop()