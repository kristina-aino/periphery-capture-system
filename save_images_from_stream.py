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
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------

from camera_capture_system.core import load_all_cameras_from_config
from camera_capture_system.fileIO import CaptureImageSaver
from camera_capture_system.datamodel import ImageParameters

if __name__ == "__main__":
    cameras = load_all_cameras_from_config(ARGS.cameras_config)
    
    cis = CaptureImageSaver(
        cameras=cameras,
        image_params=ImageParameters(
            output_format=ARGS.output_format,
            save_path=ARGS.output_path, 
            jpg_quality=ARGS.jpg_quality, 
            png_compression=ARGS.png_compression
        ),
        host=ARGS.host_name, 
        q_size=1
    )
    
    from time import sleep
    
    try:
        
        cis.start()
        
        while True:
            
            cis.save_image()
            
            sleep(1)
            
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt ...")
    except:
        raise
    finally:
        cis.stop()
        logger.info("all save image processes stopped")
