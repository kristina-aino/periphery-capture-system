import cv2
import argparse
import logging
import argparse
from traceback import format_exc

from periphery_capture_system.core import load_all_cameras_from_config, MultiInputStreamSubscriber

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("-cc", "--cameras_config", type=str, default="./cameras_configs.json", help="path to input configuration file")
AP.add_argument("--host", type=str, default="127.0.0.1", help="host name or ip of the server")

AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

logging.basicConfig(level=ARGS.logging_level.upper())
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------

if __name__ == "__main__":
    
    cameras = load_all_cameras_from_config(ARGS.cameras_config)
    mcs = MultiInputStreamSubscriber(cameras=cameras, host=ARGS.host, q_size=1)
    
    try:
        
        read_generator = mcs.start()
        
        for frame_packets in read_generator:
            
            for frame_packet in frame_packets:
                
                if frame_packet is None:
                    continue
                
                frame = frame_packet.frames
                
                cv2.imshow(frame_packet.device.uuid, frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
    except KeyboardInterrupt:
        logger.info(f"KeyboardInterrupt ...")
    except:
        logger.error(format_exc())
        raise
    finally:
        cv2.destroyAllWindows()
