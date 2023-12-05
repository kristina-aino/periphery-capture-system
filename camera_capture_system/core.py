from logging import getLogger
from datetime import datetime
from typing import List
from json import load
from traceback import format_exc
from asyncio import gather
from asyncio import run as run_async

from .camera import Camera, CameraInputReader
from .zmqIO import ZMQPublisher

#----------------------------------------

logger = getLogger(__name__)

#----------------------------------------

def load_all_cameras_from_config(config_path: str) -> List[Camera]:
    
    logger.debug(f"Loading cameras from {config_path} ...")
    
    with open(config_path, "r") as f:
        cameras = load(f)

    return [Camera(**cameras[cam_uuid], uuid=cam_uuid) for cam_uuid in cameras]


class SyncCameraCaptureAndPublish:
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
        
        self.async_camera_captures = [AsyncCameraCapture(camera, max_consec_reader_failures) for camera in cameras]
        self.async_zmq_publisher = AsyncPublisher(host_name, port)
        
        self.PUBLISHING_MODE = PUBLISHING_MODE

    def stop(self):
        for cam_cap in self.async_camera_captures:
            cam_cap.stop()
        self.async_zmq_publisher.stop()

    def start(self):
        
        try:
            while True:
                run_async(self.capture_and_publish())
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt ...")
        except:
            logger.error("Unexpected error:", format_exc())
            raise
        finally:
            self.stop()
        
    async def capture_and_publish(self):
    
        # parallel capture
        capture_futures = [cam_cap.capture() for cam_cap in self.async_camera_captures]
        results = await gather(*capture_futures)

        # filter out None results
        cam_data = [r for r in results if r is not None]
        
        # check the read time differences for each camera and for all cameras
        end_read_ts = [data["end_read_timestamp"] for _, data in cam_data]
        start_read_ts = [data["start_read_timestamp"] for _, data in cam_data]
        per_cam_read_ts_diff = [(end - start) for end, start in zip(end_read_ts, start_read_ts)]
        
        logger.debug(f"per camera read time difference: {per_cam_read_ts_diff}")
        logger.debug(f"all cameras read time difference: {max(end_read_ts) - min(start_read_ts)}")
        
        # check if all cameras have adimsiible read time differences
        # TODO
        
        # Mode selection for publishing
        if self.PUBLISHING_MODE == "ALL_AVAILABLE":
            if len(cam_data) != len(self.async_camera_captures):
                logger.warning(f"fonud {len(cam_data)}/{len(self.async_camera_captures)} cameras, publishing failed ...")
                return
        
        # publish data
        publish_futures = [self.async_zmq_publisher.publish(frame, data) for frame, data in cam_data]
        await gather(*publish_futures)
        

class AsyncCameraCapture:
    
    def __init__(self, camera: Camera, max_consec_reader_failures: int = 10):
        self.camera_reader = CameraInputReader(camera)
        self.max_consec_reader_failures = max_consec_reader_failures
        self.camera_data = camera.model_dump()
        
    def stop(self):
        self.camera_reader.close()
        
    def is_ok(self):
        return self.camera_reader.is_open()
    
    async def capture(self):
        
        assert self.is_ok(), f"AsyncCameraCapture {self.__repr__} is not ok"
        
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
        
    def stop(self):
        self.zmq_publisher.close()
        
    def is_ok(self):
        return not self.zmq_publisher.socket.closed and not self.zmq_publisher.context.closed
        
    async def publish(self, frame, data):
        
        assert self.is_ok(), f"AsyncZMQPublisher {self.__repr__} is not ok"
        
        self.zmq_publisher.publish(frame, data)
