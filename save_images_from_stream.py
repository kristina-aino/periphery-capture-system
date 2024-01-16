import argparse
import logging
import argparse

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("-cc", "--cameras_config", type=str, default="./cameras_configs.json", help="path to input configuration file")
AP.add_argument("-hn", "--host_name", type=str, default="127.0.0.1", help="host name or ip of the server")

AP.add_argument("-op", "--output_path", type=str, required=True, help="output path")
AP.add_argument("--output_format", type=str, default="jpg", help="output format", choices=["jpg", "png"])
AP.add_argument("--jpg_quality", type=int, default=100, help="jpg quality (0-100)")
AP.add_argument("--png_compression", type=int, default=3, help="png compression (0-100)")

AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

logging.basicConfig(level=ARGS.logging_level.upper())

# ---------------------------------------------------------------------

from camera_capture_system.core import load_all_cameras_from_config, MultiCaptureSubscriber
from camera_capture_system.fileIO import save_captures_as_images
from camera_capture_system.datamodel import ImageParameters

if __name__ == "__main__":
    cameras = load_all_cameras_from_config(ARGS.cameras_config)
    
    mcsb = MultiCaptureSubscriber(cameras=cameras, host=ARGS.host_name, q_size=1)
    
    video_params = ImageParameters(
        output_format=ARGS.output_format,
        save_path=ARGS.output_path, 
        jpg_quality=ARGS.jpg_quality, 
        png_compression=ARGS.png_compression)

    save_captures_as_images(mcsb, video_params)
