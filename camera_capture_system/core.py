from logging import getLogger
from datetime import datetime
from typing import List
from json import load

from .camera import Camera, CameraInputReader
from .zmqIO import ZMQPublisher

#----------------------------------------

logger = getLogger(__name__)

#----------------------------------------

def load_all_cameras_from_config(config_path: str = "./cameras_configs.json") -> List[Camera]:
    """
        Loads all cameras from a JSON configuration file.
    """
    with open(config_path, "r") as f:
        cameras = load(f)
    
    return [Camera(**camera) for camera in cameras]

class CameraPublisher(ZMQPublisher):
    """
        Publishes camera data to a ZMQ socket.
    """
    
    def __init__(
        self,
        camera: Camera,
        host_name: str = "127.0.0.1",
        port: int = 10000,
        max_consec_reader_failures: int = 10):
        
        super().__init__(host_name, port)
        self.camera_reader = CameraInputReader(camera)
        
        self.max_consec_reader_failures = max_consec_reader_failures
        
    def start(self):
        
        while self.is_ok():

            # try read frame and define metadata
            start_read_ts = datetime.now().timestamp()
            ok, frame = self.camera_reader.read()
            end_read_ts = datetime.now().timestamp()

            # count incorrect reads
            if not ok:
                logger.warning(f"{self.camera.uuid} :: reader not ok for {fail_counter}/{self.max_consec_reader_failures} frames ...")
                fail_counter += 1
                assert fail_counter <= self.max_consec_reader_failures, f"{self.camera.uuid} :: no frame found for too long of a period"
                continue
            fail_counter = 0
            
            #p publish frame and metadata
            self.publish(frame, {
                "start_read_timestamp": start_read_ts,
                "end_read_timestamp": end_read_ts,
                "camera_uuid": self.camera_reader.cam_uuid
            })
            
    def is_ok(self):
        return self.camera_reader.is_open() and not self.socket.closed and not self.context.closed

