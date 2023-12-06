from logging import getLogger
from datetime import datetime
from typing import List
from json import load
from traceback import format_exc
from asyncio import gather
from asyncio import run as run_async
from multiprocessing import Queue, Process

from .datamodel import Camera, CameraFramePacket
from .cameraIO import CameraInputReader
from .zmqIO import ZMQPublisher, ZMQSubscriber

#----------------------------------------

logger = getLogger(__name__)

#----------------------------------------

def load_all_cameras_from_config(config_path: str) -> List[Camera]:
    
    logger.debug(f"Loading cameras from {config_path} ...")
    
    with open(config_path, "r") as f:
        cameras = load(f)

    return [Camera(**cameras[cam_uuid], uuid=cam_uuid) for cam_uuid in cameras]


class MultiCameraZMQSubscriberBufferProcess:
    """
        Subsribes to a single ZMQ socket and buffers the data per camera.
    """
    
    def __init__(
        self, 
        cameras: List[Camera],
        host_name: str = "127.0.0.1",
        port: int = 10000, 
        Q_maxsize: int = 100):
        
        self.cameras = cameras
        self.zmq_sub = ZMQSubscriber(host_name, port)
        self.Q_maxsize = Q_maxsize
        
        self.frame_packet_Q = dict((cam.uuid, Queue(maxsize=self.Q_maxsize)) for cam in self.cameras)
        self.Q_sizes = dict((cam.uuid, 0) for cam in self.cameras)

        self.P = Process(target=self.buffer_frames)
        
    def stop(self):
        for cam_uuid in self.frame_packet_Q:
            self.frame_packet_Q[cam_uuid].close()
        if self.P.is_alive():
            self.P.join()
            self.P.close()
        self.zmq_sub.close()

    def start(self):
        try:
            self.P.start()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt ...")
        except:
            logger.error("Unexpected error:", format_exc())
            raise
        finally:
            self.stop()
    
    # def clear(self):
    #     for cam_uuid in self.frame_packet_Q:
    #         self.frame_packet_Q[cam_uuid].close()
    #         self.frame_packet_Q[cam_uuid] = Queue(maxsize=self.Q_maxsize)
    #         self.Q_sizes[cam_uuid] = 0
                
    def buffer_frames(self):
        while True:
            
            # record and time frame, continure if recording took too long
            frame_packet = self.zmq_sub.read()
            if not frame_packet:
                continue
            cam_uuid = frame_packet.camera.uuid
            
            # put frame into camera specific queue, and increment frame counter
            self.frame_packet_Q[cam_uuid].put(frame_packet)
            self.Q_sizes[cam_uuid] += 1
        
    def get_all_frame_packets(self) -> List[CameraFramePacket]:
        if not all([self.Q_sizes[cam_uuid] > 0 for cam_uuid in self.frame_packet_Q]):
            logger.warning("not all buffers have frames when reading")
            return None
        return [self.get_frame_packet(cam_uuid) for cam_uuid in self.frame_packet_Q]
    
    def get_frame_packet(self, cam_uuid: str) -> CameraFramePacket:
        if cam_uuid not in self.frame_packet_Q or self.Q_sizes[cam_uuid] == 0:
            logger.warning(f"{cam_uuid} :: no frames in buffer when reading")
            return None
        self.Q_sizes[cam_uuid] -= 1
        return self.frame_packet_Q[cam_uuid]

class MultiCameraCaptureAndPublish:
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
        packets = [r for r in results if r is not None]
        
        # Mode selection for publishing
        if self.PUBLISHING_MODE == "ALL_AVAILABLE":
            if len(packets) != len(self.async_camera_captures):
                logger.warning(f"fonud {len(packets)}/{len(self.async_camera_captures)} cameras, publishing failed ...")
                return
        
        
        # # check the read time differences for each camera and for all cameras
        # end_read_ts = [data["end_read_timestamp"] for _, data in cam_data]
        # start_read_ts = [data["start_read_timestamp"] for _, data in cam_data]
        # per_cam_read_ts_diff = [(end - start) for end, start in zip(end_read_ts, start_read_ts)]
        
        # logger.debug(f"per camera read time difference: {per_cam_read_ts_diff}")
        # logger.debug(f"all cameras read time difference: {max(end_read_ts) - min(start_read_ts)}")
        
        # check if all cameras have adimsiible read time differences
        # TODO
        
        # publish data
        publish_futures = [self.async_zmq_publisher.publish(p) for p in packets]
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
    
    async def capture(self) -> CameraFramePacket:
        
        assert self.is_ok(), f"AsyncCameraCapture {self.__repr__} is not ok"
        
        # try read frame and define metadata
        start_read_ts = datetime.now()
        ok, frame = self.camera_reader.read()
        end_read_ts = datetime.now()

        # count incorrect reads
        if not ok:
            logger.warning(f"{self.camera_data.uuid} :: reader not ok for {fail_counter}/{self.max_consec_reader_failures} frames ...")
            fail_counter += 1
            assert fail_counter < self.max_consec_reader_failures, f"{self.camera_data.uuid} :: no frame found for too long of a period"
            return None

        # reset fail counter
        fail_counter = 0
        
        return CameraFramePacket.create(
            frame=frame,
            data={
                "camera": self.camera_data,
                "image_data": {
                    "dtype": str(frame.dtype),
                    "shape": frame.shape
                },
                "start_read_timestamp": start_read_ts.timestamp(),
                "end_read_timestamp": end_read_ts.timestamp()
            }
        )

class AsyncPublisher:
    
    def __init__(self, host_name: str = "127.0.0.1", port: int = 10000):
        self.zmq_publisher = ZMQPublisher(host_name, port)
        
    def stop(self):
        self.zmq_publisher.close()
        
    def is_ok(self):
        return not self.zmq_publisher.socket.closed and not self.zmq_publisher.context.closed
        
    async def publish(self, frame_packet: CameraFramePacket):
        assert self.is_ok(), f"AsyncZMQPublisher {self.__repr__} is not ok"
        self.zmq_publisher.publish(frame_packet)
