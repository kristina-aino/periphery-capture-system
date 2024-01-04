from logging import getLogger, basicConfig
from traceback import format_exc
import argparse

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("-cc", "--cameras_config", type=str, default="./cameras_configs.json", help="path to input configuration file")
AP.add_argument("-hn", "--host_name", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

basicConfig(level=ARGS.logging_level.upper())
logger = getLogger(__name__)

# ---------------------------------------------------------------------

# Setp 1: read camera configurations for all cameras
from camera_capture_system.core import load_all_cameras_from_config, MultiCapturePublisher


if __name__ == "__main__":
    try:
        cameras = load_all_cameras_from_config(ARGS.cameras_config)
        mcp = MultiCapturePublisher(cameras=cameras, host=ARGS.host_name)
        
        mcp.start()
        
    except KeyboardInterrupt:
        logger.info(f"KeyboardInterrupt ...")
    except:
        logger.error(format_exc())
        raise