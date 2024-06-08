import time
import argparse

from logging import getLogger, basicConfig
from traceback import format_exc

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("--config", type=str, default="./configs/devices.json", help="path to device config file")
AP.add_argument("--port", type=int, default=10000, help="port number to stream video")
AP.add_argument("--host", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

basicConfig(level=ARGS.logging_level.upper())
logger = getLogger(__name__)

# ---------------------------------------------------------------------

# Setp 1: read camera configurations for all cameras
from periphery_capture_system.core import InputStreamSender, InputStreamReciever
from periphery_capture_system.deviceIO import CameraDeviceReader, load_all_devices_from_config
from periphery_capture_system.zmqIO import ZMQSender, ZMQReciever

if __name__ == "__main__":
    
    camera = load_all_devices_from_config("video", config_file=ARGS.config)[0]
    
    sender = InputStreamSender(
        device_reader=CameraDeviceReader(camera),
        zmq_sender=ZMQSender(host=ARGS.host, port=ARGS.port)
    )
    reciever = InputStreamReciever(
        ZMQReciever(host=ARGS.host, port=ARGS.port)
    )
    
    try:
        sender.start_process()
        reciever.start_process()
        
        print("Streaming video...")
        for i in range(10):
            
            print(reciever.read())
            
            time.sleep(1)
        
    except Exception as e:
        print(e.with_traceback())
        raise e
    finally:
        sender.stop_process()
        reciever.stop_process()