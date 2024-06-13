import time
import argparse
import logging
import argparse

from datetime import datetime

from device_capture_system.deviceIO import load_all_devices_from_config
from device_capture_system.core import MultiInputStreamSender
from device_capture_system.datamodel import FramePreprocessing
from device_capture_system.fileIO import ImageSaver

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("--config", type=str, default="./configs/devices.json", help="path to device configuration file")
AP.add_argument("--host", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("--proxy_sub_port", type=int, default=10000, help="port for proxy subscriber")
AP.add_argument("--proxy_pub_port", type=int, default=10001, help="port for proxy publisher")

AP.add_argument("--output_path", type=str, required=True, help="output path")
AP.add_argument("--image_file_extension", type=str, default="jpg", help="image file extension", choices=["jpg", "png"])
AP.add_argument("--jpg_quality", type=int, default=95, help="jpg quality")
AP.add_argument("--png_compression", type=int, default=3, help="png compression level")

AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

logging.basicConfig(level=ARGS.logging_level.upper())
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------

if __name__ == "__main__":
    
    cameras = load_all_devices_from_config("video", config_file=ARGS.config)
    
    image_saver = ImageSaver(
        cameras=cameras,
        proxy_pub_port=ARGS.proxy_pub_port,
        output_path=ARGS.output_path,
        image_file_extension=ARGS.image_file_extension,
        jpg_quality=ARGS.jpg_quality,
        png_compression=ARGS.png_compression,
        host=ARGS.host
    )
    
    input_stream_sender = MultiInputStreamSender(
        devices=cameras,
        proxy_sub_port=ARGS.proxy_sub_port,
        proxy_pub_port=ARGS.proxy_pub_port,
        host=ARGS.host,
        frame_preprocessings=[
            FramePreprocessing.ROTATE_90_CLOCKWISE,
            FramePreprocessing.ROTATE_90_CLOCKWISE,
            FramePreprocessing.ROTATE_90_COUNTERCLOCKWISE
        ]
    )
    
    
    try:
        
        input_stream_sender.start_processes()
        image_saver.start()
        
        image_saver.save_images(50)
        
    except Exception as e:
        raise e
    finally:
        image_saver.stop()
        input_stream_sender.stop_processes()
