from time import sleep
from logging import getLogger
from typing import List
from json import load
from traceback import format_exc
from multiprocessing import Process, Event

from .datamodel import Camera
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

class ZMQPublisherProcessWithBuffer:
    """
        Publishes data from a single camera to a ZMQ socket, as a process.
        The process should be recoverable
        
        #TODO
    """
    
    def __init__(self):
        return NotImplemented

class MultiCaptureSubscriber:
    """
        Subsribes to a list of ZMQ sockets and returns the data.
    """
    
    def __init__(self, cameras: List[Camera], host: str = "127.0.0.1"):
        
        self.cameras = cameras
        self.zmq_subscribers = [ZMQSubscriber(host, cam.publishing_port) for cam in cameras]
        
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
            logger.error(format_exc())
            raise
        finally:
            self.stop()


class CapturePublisher:
    """
        Publishes data from a single camera to a ZMQ socket.
    """
    
    def __init__(self, camera: Camera, host: int = "127.0.0.1", stop_event: Event = None):
        
        self.camera = camera
        self.host = host
        
        # for multiprocessing
        self.stop_event = stop_event
        
    def start(self):
        
        logger.info(f"{self.camera.uuid} :: starting capture publisher")
        
        try:

            zmq_publisher = ZMQPublisher(self.host, self.camera.publishing_port)
            capture = CameraInputReader(self.camera)
        
        
            while self.stop_event is None or not self.stop_event.is_set():
                
                assert zmq_publisher.is_ok(), f"{self.camera.uuid} :: zmq publisher is not ok"
                
                # read frame from capture
                frame_packet = capture.read()
                
                if frame_packet is None:
                    logger.warning(f"{self.camera.uuid} :: capture publisher failed to read frame")
                    continue
                
                # publish frame
                zmq_publisher.publish(frame_packet)
                
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt ...")
        except:
            logger.error(format_exc())
            raise
        finally:
            zmq_publisher.close()
            capture.close()


class MultiCapturePublisher:
    """
        Publishes multiple cameras data to individual ZMQ sockets.
    """
    
    def __init__(self, cameras: List[Camera], host: str = "127.0.0.1"):
        
        self.cameras = cameras
        self.stop_events = [Event() for _ in cameras]
        
        self.capture_publishers = {cam.uuid: CapturePublisher(cam, host, stop_event) for cam, stop_event in zip(cameras, self.stop_events)}
        self.capture_publishers_processes = {}
        
    def stop(self):
        for event in self.stop_events:
            event.set()
        for process in self.capture_publishers_processes.values():
            if process.is_alive():
                process.join()
        logger.info("multi cam capture and publish stopped")
        
    def start(self):
        
        logger.info("starting multi cam capture and publish ...")
        try:
            # start all capture publishers processes
            for k in self.capture_publishers:
                self.capture_publishers_processes[k] = Process(target=self.capture_publishers[k].start)
                self.capture_publishers_processes[k].start()
                
        except:
            for event in self.stop_events:
                event.set()
            for process in self.capture_publishers_processes.values():
                if process.is_alive():
                    process.terminate()
                    process.join()
            logger.error(format_exc())
            raise
        
        try:
            while True:
                
                # check if any of the processes have stopped
                for k in self.capture_publishers:
                    if not self.capture_publishers_processes[k].is_alive():
                        logger.warning(f"capture publisher for {k} has stopped")
                        # self.restart(k)
                        raise Exception(f"capture publisher for {k} has stopped")
                
                sleep(0.5)
                
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt ...")
        except:
            logger.error(format_exc())
            raise
        finally:
            self.stop()
    
    def restart(self, cam_uuid):
        
        logger.info(f"restarting capture publisher for {self.cameras[cam_uuid].uuid} ...")
        
        self.stop_events[cam_uuid].set()
        self.capture_publishers_processes[cam_uuid].join()
        self.stop_events[cam_uuid].clear()
        self.capture_publishers_processes[cam_uuid] = Process(target=self.capture_publishers[cam_uuid].start)
        self.capture_publishers_processes[cam_uuid].start()