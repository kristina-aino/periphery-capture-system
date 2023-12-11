import cv2
import argparse
import logging
import argparse
from traceback import format_exc

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("-cc", "--cameras_config", type=str, default="./cameras_configs.json", help="path to input configuration file")
AP.add_argument("-hn", "--host_name", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("-p", "--ports", nargs="+", default=[10000, 10001], help="ports to opsn zmq socket on")

AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

logging.basicConfig(level=ARGS.logging_level.upper())
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------

from camera_capture_system.core import load_all_cameras_from_config, MultiCameraZMQSubscriber

if __name__ == "__main__":
    
    cameras = load_all_cameras_from_config(ARGS.cameras_config)
    mcs = MultiCameraZMQSubscriber(cameras=cameras, host_name=ARGS.host_name, ports=ARGS.ports)
    
    try:
        
        for frame_packets in mcs.receive():
            
            for frame_packet in frame_packets:
                
                if frame_packet is None:
                    continue
                
                frame = frame_packet.camera_frame
                
                cv2.imshow(frame_packet.camera.uuid, frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
    except KeyboardInterrupt:
        logger.info(f"KeyboardInterrupt ...")
    except:
        logger.error("Unexpected error:", format_exc())
        raise
    finally:
        cv2.destroyAllWindows()
