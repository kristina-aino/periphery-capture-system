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

# # meant to be run in a separate process
# def buffer_frames(host_name: str, port: int, frame_packet_Q: dict):
    
#     zmq_sub = ZMQSubscriber(host_name, port)

#     try:    
#         while True:
#             # record and time frame, continure if recording took too long
#             frame_packet = zmq_sub.recieve()
#             if not frame_packet:
#                 continue
            
#             # drop frame if buffer is full
#             if frame_packet_Q[frame_packet.camera.uuid].full():
#                 logger.warning(f"{frame_packet.camera.uuid} :: buffer full, dropping frame ...")
#                 frame_packet_Q[frame_packet.camera.uuid].get()
                
#             # put frame into camera specific queue, and increment frame counter
#             frame_packet_Q[frame_packet.camera.uuid].put(frame_packet)
#     except KeyboardInterrupt:
#         logger.info(f"KeyboardInterrupt ...")
#     except:
#         logger.error("Unexpected error:", format_exc())
#         raise
#     finally:
#         zmq_sub.close()

# class MultiCameraZMQSubscriberBufferProcess:
#     """
#         Subsribes to a single ZMQ socket and buffers the data per camera.
#     """
    
#     def __init__(
#         self, 
#         cameras: List[Camera],
#         host_name: str = "127.0.0.1",
#         port: int = 10000,
#         Q_maxsize: int = 100,
#         queue_read_timeout: float = 2):
                
#         self.cameras = cameras
#         self.frame_packet_Q = dict((cam.uuid, Queue(maxsize=Q_maxsize)) for cam in self.cameras)
        
#         self.P = Process(target=buffer_frames, args=(
#             host_name,
#             port,
#             self.frame_packet_Q
#         ), daemon=True)
                
#         self.queue_read_timeout = queue_read_timeout
                
#     def start(self):
        
#         logger.info("starting MultiCameraZMQSubscriberBufferProcess ...")
        
#         try:
#             self.P.start()
#         except KeyboardInterrupt:
#             logger.info("KeyboardInterrupt ...")
#         except:
#             logger.error("Unexpected error:", format_exc())
#             raise
        
#     def get_frame_packets(self) -> List[CameraFramePacket]:
#         # if any([self.frame_packet_Q[cam_uuid].empty() for cam_uuid in self.frame_packet_Q]):
#         #     logger.warning("not all buffers have frames when reading")
#         #     return None
#         try:
#             frame_packets = [self.frame_packet_Q[cam_uuid].get(timeout=self.queue_read_timeout) for cam_uuid in self.frame_packet_Q]
#             return frame_packets
#         except TimeoutError:
#             logger.warning("not all buffers have frames when reading")
#             return None
        
#     def stop(self):
#         for cam_uuid in self.frame_packet_Q:
#             self.frame_packet_Q[cam_uuid].close()
#         if self.P.is_alive():
#             self.P.terminate()
#             self.P.join()
#             self.P.close()
#         logger.info("buffered subscriber process stopped")


class ZMQPublisherProcessWithBuffer:
    """
        Publishes data from a single camera to a ZMQ socket, as a process.
        The process should be recoverable
        
        #TODO
    """
    
    def __init__(self):
        return NotImplemented


class MultiCameraZMQSubscriber:
    """
        Subsribes to a list of ZMQ sockets and returns the data.
    """
    
    def __init__(
        self, 
        cameras: List[Camera],
        ports: List[int],
        host_name: str = "127.0.0.1"):
        
        self.cameras = cameras
        self.zmq_subscribers = [ZMQSubscriber(host_name, port) for port in ports]
        
    def is_ok(self):
        return all([zmq_sub.is_ok() for zmq_sub in self.zmq_subscribers])
        
    def stop(self):
        for zmq_sub in self.zmq_subscribers:
            zmq_sub.close()
        logger.info("multi cam subscriber stopped")
        
    def receive(self):
        
        try:
            assert self.is_ok(), "not all subscribers are ok"
            
            while True:
                packages = [zmq_sub.recieve() for zmq_sub in self.zmq_subscribers]
                
                yield packages
            
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt ...")
        except:
            logger.error("Unexpected error:", format_exc())
            raise
        finally:
            self.stop()

class MultiCameraCaptureAndPublish:
    """
        Publishes multiple cameras data to a single ZMQ socket.
    """
    
    def __init__(
        self,
        cameras: List[Camera],
        ports: List[int],
        host_name: str = "127.0.0.1",
        max_consec_reader_failures: int = 10,
        PUBLISHING_MODE: str = "ALL_AVAILABLE"):
        
        assert len(cameras) == len(ports), "number of cameras and ports must be equal"
        
        # TODO: add additional modes for publishing
        
        self.async_camera_captures = [CameraInputReader(camera, max_consec_reader_failures) for camera in cameras]
        self.async_zmq_publishers = [ZMQPublisher(host_name, port) for port in ports]
        
        self.PUBLISHING_MODE = PUBLISHING_MODE
        
    def stop(self):
        for cam_cap in self.async_camera_captures:
            cam_cap.close()
        for zmq_pub in self.async_zmq_publishers:
            zmq_pub.close()
        logger.info("multi cam capture and publish stopped")
        
    def start(self):
        logger.info("starting multi cam capture and publish ...")
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
        capture_futures = [cam_cap.async_read() for cam_cap in self.async_camera_captures]
        results = await gather(*capture_futures)
        
        # filter out None results
        packets = [r for r in results if r is not None]
        
        # Mode selection for publishing
        if self.PUBLISHING_MODE == "ALL_AVAILABLE":
            if len(packets) != len(self.async_camera_captures):
                logger.warning(f"fonud {len(packets)}/{len(self.async_camera_captures)} cameras, publishing failed ...")
                return
        
        # # calculate the time difference between the frames
        # start_read_time_ts = [p.start_read_dt.timestamp() for p in packets]
        # end_read_time_ts = [p.end_read_dt.timestamp() for p in packets]
        
        # current_start_read_ts = min(start_read_time_ts)
        # current_end_read_ts = max(end_read_time_ts)
        
        # logger.debug(f"frame rate : {1/(current_start_read_ts - last_start_read_ts)}")
        # logger.debug(f"frame rate : {1/(current_end_read_ts - last_end_read_ts)}")
        
        # last_start_read_ts = current_start_read_ts
        # last_end_read_ts = current_end_read_ts
        
        # # check the read time differences for each camera and for all cameras
        # end_read_ts = [data["end_read_timestamp"] for _, data in cam_data]
        # start_read_ts = [data["start_read_timestamp"] for _, data in cam_data]
        # per_cam_read_ts_diff = [(end - start) for end, start in zip(end_read_ts, start_read_ts)]
        
        # logger.debug(f"per camera read time difference: {per_cam_read_ts_diff}")
        # logger.debug(f"all cameras read time difference: {max(end_read_ts) - min(start_read_ts)}")
        
        # check if all cameras have adimsiible read time differences
        # TODO
        
        # publish data
        publish_futures = [zmq_pub.async_publish(p) for (zmq_pub, p) in zip(self.async_zmq_publishers, packets)]
        await gather(*publish_futures)
