from numpy import argmax
from time import sleep
from logging import getLogger
from typing import List, Callable
from json import load
from traceback import format_exc
from multiprocessing import Process, Event, Queue
from datetime import datetime, timedelta
from queue import Empty as QueueEmpty
from queue import Full as QueueFull

from .datamodel import Camera, CameraFramePacket
from .cameraIO import CameraInputReader
from .zmqIO import ZMQPublisher, ZMQSubscriber

#----------------------------------------

logger = getLogger(__name__)

#----------------------------------------

def load_all_cameras_from_config(config_path: str) -> List[Camera]:
    logger.debug(f"{__name__} :: loading cameras from config file ...")
    with open(config_path, "r") as f:
        cameras = load(f)
    return [Camera(**cameras[cam_uuid], uuid=cam_uuid) for cam_uuid in cameras]

class CaptureSubscriber:
    """
        Subscribes to a ZMQ socket and returns the data.
    """
    
    def __init__(self, camera: Camera, q_size: int, host: str = "127.0.0.1"):
        
        self.logger_suffix = f"{self.__class__.__name__} :: {camera.uuid} -"
        
        self.camera = camera
        self. host = host
        
        self.queue_empty_event = Event()
        
        self.stop_event = Event()
        self.output_queue = Queue(maxsize=q_size)
        self.q_size = q_size
        self.process = None
        
    def start_process(self):
        
        logger.info(f"{self.logger_suffix} starting ...")
        
        if self.process is not None:
            logger.warning(f"{self.logger_suffix} trying to start a process that has already started")
            return
        
        self.stop_event.clear()
        process = Process(target=self._start)
        process.start()
        self.process = process
        
        logger.info(f"{self.logger_suffix} started !")
        
    def stop_process(self, terminate: bool):
        
        logger.info(f"{self.logger_suffix} stopping ...")
        
        if self.process is None:
            logger.warning(f"{self.logger_suffix} trying to stop a process that has not started")
            return
        
        self.output_queue.close()
        
        self.stop_event.set()
        self.process.join(timeout=1)
        if terminate:
            self.process.terminate()
        self.process = None
        
        logger.info(f"{self.logger_suffix} stopped !")
        
    def _start(self, block: bool = False, timeout: float = 1):
        
        logger.info(f"{self.logger_suffix} starting ...")
        
        try:
            
            zmq_subscriber = ZMQSubscriber(self.host, self.camera.publishing_port)
            
            while self.stop_event is None or not self.stop_event.is_set():
                
                assert zmq_subscriber.is_ok(), f"{self.camera.uuid} :: zmq subscriber is not ok"
                
                # dont add frame if queue is being emptied
                if self.queue_empty_event.is_set():
                    continue
                
                # read frame from capture and put in queue
                try:
                    frame_packet = zmq_subscriber.recieve()
                    self.output_queue.put(frame_packet, block=block, timeout=timeout)
                except QueueFull:
                    # logger.warning(f"{self.camera.uuid} :: capture subscriber queue is full, dropping frame")
                    continue
                except KeyboardInterrupt:
                    logger.info("KeyboardInterrupt ...")
                    break
        except:
            raise
        finally:
            zmq_subscriber.close()
            
    def read(self, block: bool = False, timeout: float = 1):
        try:
            return self.output_queue.get(block=block, timeout=timeout)
        except QueueEmpty:
            return None
        except:
            raise
        

class MultiCaptureSubscriber:
    """
        Subsribes to a list of ZMQ sockets as processes and returns the data.
        
        ! calling stop() at termination is the responsibility of the caller !
    """
    
    def __init__(self, cameras: List[Camera], q_size: int, host: str = "127.0.0.1"):
        
        self.logger_suffix = f"{self.__class__.__name__} -"
        
        self.capture_subscribers = {cam.uuid: CaptureSubscriber(cam, q_size, host) for cam in cameras}
        
        self.last_frames_datetime = None
        
    def stop(self, terminate : bool = True):
        logger.info(f"{self.logger_suffix} starting ...")
        
        # stop all capture subscribers processes and wait for cleanup
        for capture_subscriber in self.capture_subscribers.values():
            capture_subscriber.stop_process(terminate=terminate)
            
        logger.info(f"{self.logger_suffix} stopped !")
        
    def start(self):
        
        logger.info(f"{self.logger_suffix} starting ...")
        
        # start reading from all cameras
        for capture_subscriber in self.capture_subscribers.values():
            capture_subscriber.start_process()
            
        logger.info(f"{self.logger_suffix} started !")
        
    def read(self, block: bool = False, timeout: float = 1, synchronous_read: bool = False) -> List[CameraFramePacket]:
        
        # read from all camera subseiber
        frame_packets = [self.capture_subscribers[k].read(block=block, timeout=timeout) for k in self.capture_subscribers]
        
        # return if any packets are None
        for packet in frame_packets:
            if packet is None:
                return None
        
        if not synchronous_read:
            return frame_packets
        
        # syncronize frames
        # compute last frames datetime on first read
        if self.last_frames_datetime is None:
            self.last_frames_datetime = [*map(lambda a: a.end_read_dt, frame_packets)]
            return frame_packets
        
        most_recent_last_frame_dt = max(self.last_frames_datetime)
        
        for i in range(len(frame_packets)):
            while frame_packets[i].end_read_dt < most_recent_last_frame_dt:
                new_frame = self.capture_subscribers[frame_packets[i].camera.uuid].read(block=True, timeout=timeout)
                
                if new_frame is None:
                    logger.warn(f"{self.logger_suffix} failed to read next frame")
                    sleep(0.1)
                
                self.last_frames_datetime[i] = frame_packets[i].end_read_dt
                frame_packets[i] = new_frame
        
        return frame_packets
    
    def empty_queues(self):
        
        logger.info(f"{self.logger_suffix} emptying capture queues ...")
        
        # set empty queue event
        for capture_subscriber in self.capture_subscribers.values():
            capture_subscriber.queue_empty_event.set()
        
        for capture_subscriber in self.capture_subscribers.values():
            while capture_subscriber.output_queue.qsize() > 0:
                
                try:
                    capture_subscriber.output_queue.get(timeout=1)
                except ValueError:
                    logger.warning(f"{self.logger_suffix} failed to empty queue")
                    break
        
        # clear empty queue event
        for capture_subscriber in self.capture_subscribers.values():
            capture_subscriber.queue_empty_event.clear()
        
        logger.info(f"{self.logger_suffix} queues emptied !")

class CapturePublisher:
    """
        Publishes data from a single camera to a ZMQ socket.
    """
    
    def __init__(self, camera: Camera, host: int = "127.0.0.1", frame_transform: str = None):
        
        self.logger_suffix = f"{self.__class__.__name__} :: {camera.uuid} -"
        
        self.camera = camera
        self.host = host
        self.frame_transform = frame_transform
        
        # for multiprocessing
        self.stop_event = Event()
        self.process = None
        
    def start_process(self):
        
        logger.info(f"{self.logger_suffix} starting process ...")
        
        if self.process is not None:
            logger.warning(f"{self.logger_suffix} trying to start a process that has already started")
            return
        
        self.stop_event.clear()
        process = Process(target=self._start)
        process.start()
        self.process = process
        
        logger.info(f"{self.logger_suffix} process started !")
        
    def stop_process(self, terminate=False):
        
        logger.info(f"{self.logger_suffix} process stopping ...")
        
        if self.process is None:
            logger.warning(f"{self.logger_suffix} trying to stop process that has not started")
            return
        
        self.stop_event.set()
        if terminate:
            self.process.terminate()
        self.process.join()
        self.process = None
        
        logger.info(f"{self.logger_suffix} process stopped !")
        
    def _start(self):
        
        logger.info(f"{self.logger_suffix} starting capture publisher")
        
        zmq_publisher = ZMQPublisher(self.host, self.camera.publishing_port)
        capture = CameraInputReader(self.camera, frame_transform=self.frame_transform)
        
        try:
            
            
            while self.stop_event is None or not self.stop_event.is_set():
                
                assert zmq_publisher.is_ok(), f"{self.logger_suffix} zmq publisher is not ok"
                
                # read frame from capture
                frame_packet = capture.read()
                
                if frame_packet is None:
                    logger.warning(f"{self.logger_suffix} failed to read frame")
                    continue
                
                # publish frame
                zmq_publisher.publish(frame_packet)
                
        except KeyboardInterrupt:
            logger.info(f"{self.logger_suffix} KeyboardInterrupt ...")
        except:
            raise
        finally:
            # close zmq publisher and capture from inside the process
            zmq_publisher.close()
            capture.close()

class MultiCapturePublisher:
    """
        Publishes multiple cameras data to individual ZMQ sockets.
        
        ! if background is set, the calling process is responsible for calling stop() at termination !
    """
    
    def __init__(self, cameras: List[Camera], host: str = "127.0.0.1", frame_transforms: dict[str, str] = {}):
        
        self.logger_suffix = f"{self.__class__.__name__} -"
        
        assert len(cameras) > 0, "no cameras provided"
        
        self.capture_publishers = {cam.uuid: CapturePublisher(cam, host, frame_transforms.get(cam.uuid, None)) for cam in cameras}
        
    def stop(self, terminate=False):
        # stop all capture publishers processes and wait for cleanup (unless terminate is set, then terminate immediately)
        logger.info(f"{self.logger_suffix} stopping ...")
        
        for capture_publisher in self.capture_publishers.values():
            capture_publisher.stop_process(terminate=terminate)
            
        logger.info(f"{self.logger_suffix} stopped !")
        
    def start(self, background: bool = True):
        
        logger.info(f"{self.logger_suffix} starting ...")
        try:
            # start all capture publishers processes
            for capture_publisher in self.capture_publishers.values():
                capture_publisher.start_process()
        except:
            self.stop(terminate=True)
            raise
        logger.info(f"{self.logger_suffix} started !")
        
        if background:
            return
        
        try:
            while True:
                
                # check if any of the processes have stopped and restart if desired
                for capture_publisher in self.capture_publishers.values():
                    
                    if capture_publisher.process is None:
                        raise Exception(f"{self.logger_suffix} {capture_publisher.camera.uuid} has not started")
                    
                    if not capture_publisher.process.is_alive():
                        # TODO: self.restart(k)
                        raise Exception(f"{self.logger_suffix} {capture_publisher.camera.uuid} has stopped")
                
                sleep(0.5)
                
        except KeyboardInterrupt:
            logger.info(f"{self.logger_suffix} KeyboardInterrupt ...")
        except:
            raise
        finally:
            self.stop()
        
    def restart(self, cam_uuid):
        logger.info(f"{self.logger_suffix} restarting {self.cameras[cam_uuid].uuid} ...")
        self.capture_publishers[cam_uuid].stop_process()
        self.capture_publishers[cam_uuid].start_process()