from logging import getLogger
from datetime import datetime
from typing import List
from json import load
import asyncio

from .camera import Camera, CameraInputReader
from .zmqIO import ZMQPublisher

#----------------------------------------

logger = getLogger(__name__)

#----------------------------------------

def load_all_cameras_from_config(config_path: str = "./cameras_configs.json") -> List[Camera]:
    
    logger.debug(f"Loading cameras from {config_path} ...")
    
    with open(config_path, "r") as f:
        cameras = load(f)
    return [Camera(**camera) for camera in cameras]


class ParallelCameraCaptureAndPublish(ZMQPublisher):
    """
        Publishes multiple cameras data to a single ZMQ socket.
    """
    
    def __init__(
        self,
        cameras: List[Camera],
        host_name: str = "127.0.0.1",
        port: int = 10000,
        max_consec_reader_failures: int = 10,
        PUBLISHING_MODE: str = "ALL_AVAILABLE"):
        
        # TODO: add functionality to publish on multiple sockets if required
        # TODO: add additional modes for publishing
        
        self.camera_captures = [AsyncCameraCapture(camera, max_consec_reader_failures) for camera in cameras]
        self.zmq_publisher = AsyncPublisher(host_name, port)
        
        self.PUBLISHING_MODE = PUBLISHING_MODE
        
    async def start(self):
        
        # parallel capture
        capture_futures = [cam_cap.capture() for cam_cap in self.camera_captures]
        results = await asyncio.gather(*capture_futures)

        # filter out None results        
        cam_data = [r for r in results if r is not None]
        
        
        # check the read time differences for each camera and for all cameras
        end_read_ts = [data["end_read_timestamp"] for _, data in cam_data]
        start_read_ts = [data["start_read_timestamp"] for _, data in cam_data]
        
        
        
        
        # Mode selection for publishing
        if self.PUBLISHING_MODE == "ALL_AVAILABLE":
            if len(cam_data) != len(self.camera_captures):
                logger.warning(f"fonud {len(cam_data)}/{len(self.camera_captures)} cameras, publishing failed ...")
                return
        
        
        publish_futures = [self.zmq_publisher.publish(frame, data) for frame, data in cam_data]
        await asyncio.gather(*publish_futures)
        

class AsyncCameraCapture:
    
    def __init__(self, camera: Camera, max_consec_reader_failures: int = 10):
        self.camera_reader = CameraInputReader(camera)
        self.max_consec_reader_failures = max_consec_reader_failures
        self.camera_data = camera.model_dump()
        
    def is_ok(self):
        return self.camera_reader.is_open()
    
    async def capture(self):
        
        # try read frame and define metadata
        start_read_ts = datetime.now().timestamp()
        ok, frame = self.camera_reader.read()
        end_read_ts = datetime.now().timestamp()

        # count incorrect reads
        if not ok:
            logger.warning(f"{self.camera.uuid} :: reader not ok for {fail_counter}/{self.max_consec_reader_failures} frames ...")
            fail_counter += 1
            assert fail_counter < self.max_consec_reader_failures, f"{self.camera.uuid} :: no frame found for too long of a period"
            return None

        # reset fail counter
        fail_counter = 0
        
        return frame, {
            "start_read_timestamp": start_read_ts,
            "end_read_timestamp": end_read_ts,
            "camera_data": self.camera_data
        }

class AsyncPublisher:
    
    def __init__(self, host_name: str = "127.0.0.1", port: int = 10000):
        self.zmq_publisher = ZMQPublisher(host_name, port)
        
    def is_ok(self):
        return not self.zmq_publisher.socket.closed and not self.zmq_publisher.context.closed
        
    async def publish(self, frame, data):
        
        assert self.is_ok(), f"ZMQPublisher {self.__repr__} is not ok"
        
        self.zmq_publisher.publish(frame, data)
