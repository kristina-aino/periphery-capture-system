import cv2
import argparse
import logging
import argparse
from traceback import format_exc

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("-cc", "--cameras_config", type=str, default="./cameras_configs.json", help="path to input configuration file")
AP.add_argument("-hn", "--host_name", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("-p", "--port", type=int, default=10000, help="port to opsn zmq socket on")
AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
AP.add_argument("-ql", "--queue_length", type=int, default=100, help="queue length for the camera specific qureues")
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

logging.basicConfig(level=ARGS.logging_level.upper())
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------

from camera_capture_system.core import load_all_cameras_from_config, MultiCameraZMQSubscriberBufferProcess
from camera_capture_system.fileIO import write_videos_from_zmq_stream
from camera_capture_system.datamodel import VideoParameters

if __name__ == "__main__":
    cameras = load_all_cameras_from_config(ARGS.cameras_config)
    mcsb = MultiCameraZMQSubscriberBufferProcess(
        cameras=cameras,
        host_name=ARGS.host_name,
        port=ARGS.port,
        Q_maxsize=ARGS.queue_length)

    try:
        
        mcsb.start()
        
        while True:
            
            frame_packets = mcsb.get_frame_packets()
            
            for frame_packet in frame_packets:
                
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
        mcsb.stop()
        cv2.destroyAllWindows()
