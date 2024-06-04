from typing import Union
from time import sleep
from logging import getLogger
from typing import List
from multiprocessing import Process, Event, Queue
from queue import Empty as QueueEmpty
from queue import Full as QueueFull

from .datamodel import FramePacket, PeripheryDevice, CameraDevice, AudioDevice
from .deviceIO import CameraInputDevice, AudioInputDevice
from .zmqIO import ZMQSender, ZMQReciever


# ------------- Subscribers -------------

class InputStreamSender:
    def __init__(
        self, 
        device: PeripheryDevice,
        host: str = "127.0.0.1", 
        frame_transform: str = None):
        
        self.logger = getLogger(f"{self.__class__.__name__}:{device.uuid}")
        
        self.device = device
        self.host = host
        self.frame_transform = frame_transform
        
        # for multiprocessing
        self.stop_event = Event()
        self.process = None
        
    def start_process(self):
        
        self.logger.info("starting process ...")
        
        if self.process is not None:
            self.logger.warning("trying to start a process that has already started")
            return
        
        self.stop_event.clear()
        self.process = Process(target=self.run_)
        self.process.start()
        
        self.logger.info("process started !")
        
    def stop_process(self, terminate=False):
        
        self.logger.info("process stopping ...")
        
        if self.process is None:
            self.logger.warning("trying to stop process that has not started")
            return
        
        self.stop_event.set()
        if terminate:
            self.process.terminate()
        self.process.join()
        self.process = None
        
        self.logger.info("process stopped !")
        
    def run_(self):
        
        self.logger.info("starting capture publisher")
        
        zmq_sender = ZMQSender(self.host, self.device.publishing_port)
        
        # create capture device depending on device type
        if type(self.device) == CameraDevice:
            capture = CameraInputDevice(camera=self.device, frame_transform=self.frame_transform)
        elif type(self.device) == AudioDevice:
            capture = AudioInputDevice(audio_device=self.device)
        else:
            zmq_sender.close()
            capture.stop()
            raise Exception("invalid device type")
        
        try:
            
            while self.stop_event is None or not self.stop_event.is_set():
                
                if not zmq_sender.is_ok():
                    raise Exception("zmq publisher is not ok")
                
                # read frame from capture
                frame_packet = capture.read()
                if frame_packet is None:
                    self.logger.warning("failed to read frame")
                    continue
                
                # send frame
                ret = zmq_sender.send(frame_packet)
                
                if ret is None:
                    self.logger.warning("failed to send frame")
                    continue
                
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt ...")
        except Exception as e:
            raise e
        finally:
            # close zmq publisher and capture from inside the process
            zmq_sender.close()
            capture.stop()

class InputStreamReciever:
    
    def __init__(
        self, 
        device: PeripheryDevice, 
        q_size: int, 
        host: str = "127.0.0.1"):
        
        self.logger = getLogger(f"{self.__class__.__name__}:{device.uuid}" )
        
        self.device = device
        self.host = host
        
        self.queue_empty_event = Event()
        
        self.stop_event = Event()
        self.output_queue = Queue(maxsize=q_size)
        self.q_size = q_size
        self.process = None
        
    def start_process(self):
        
        self.logger.info("starting ...")
        
        if self.process is not None:
            self.logger.warning("trying to start a process that has already started")
            return
        
        self.stop_event.clear()
        process = Process(target=self.run_)
        process.start()
        self.process = process
        
        self.logger.info("started !")
        
    def stop_process(self, terminate: bool):
        
        self.logger.info("stopping ...")
        
        if self.process is None:
            self.logger.warning("trying to stop a process that has not started")
            return
        
        self.output_queue.close()
        
        self.stop_event.set()
        self.process.join(timeout=1)
        if terminate:
            self.process.terminate()
        self.process = None
        
        self.logger.info("stopped !")
        
    def run_(self, block: bool = False, timeout: float = 1):
        
        self.logger.info("starting ...")
        
        try:
            zmq_subscriber = ZMQSubscriber(self.host, self.device.publishing_port)
            
            while self.stop_event is None or not self.stop_event.is_set():
                
                # dont add frame if queue is being emptied
                if self.queue_empty_event.is_set():
                    continue
                
                # read frame from capture and put in queue
                try:
                    frame_packet = zmq_subscriber.recieve()
                    self.output_queue.put(frame_packet, block=block, timeout=timeout)
                except QueueFull:
                    self.logger.debug("queue full")
                    continue
                except KeyboardInterrupt:
                    self.logger.info("KeyboardInterrupt ...")
                    break
        except:
            raise
        finally:
            zmq_subscriber.close()
        
    def read(self, block: bool = False, timeout: float = 1):
        try:
            return self.output_queue.get(block=block, timeout=timeout)
        except QueueEmpty:
            self.logger.debug("queue empty returning None ...")
            return None
        except:
            raise


class MultiInputStreamSubscriber:
    """
        Subsribes to a list of ZMQ sockets as processes and returns the data.
        
        ! calling stop() at termination is the responsibility of the caller !
    """
    
    def __init__(self, devices: List[Union[Camera, AudioDevice]], q_size: int, host: str = "127.0.0.1"):
        self.logger = getLogger(self.__class__.__name__)
        self.capture_subscribers = {device.uuid: InputStreamSubscriber(device, q_size, host) for device in devices}
        self.last_frames_datetime = None
        
    def stop(self, terminate : bool = True):
        self.logger.info("starting ...")
        
        # stop all capture subscribers processes and wait for cleanup
        for capture_subscriber in self.capture_subscribers.values():
            capture_subscriber.stop_process(terminate=terminate)
        
        self.logger.info("stopped !")
        
    def start(self):
        self.logger.info("starting ...")
        
        # start reading from all cameras
        for capture_subscriber in self.capture_subscribers.values():
            capture_subscriber.start_process()
        
        self.logger.info("started !")
        
    def read(self, block: bool = False, timeout: float = 1, synchronous_read: bool = False) -> Union[List[FramePacket], None]:
        
        # read from all camera subseiber
        frame_packets = [self.capture_subscribers[k].read(block=block, timeout=timeout) for k in self.capture_subscribers]
        
        self.logger.debug(f"valid frame packets: {[f is not None for f in frame_packets]}")
        
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
        
        # read frames until all datetimes line up as accuratl as possible
        most_recent_last_frame_dt = max(self.last_frames_datetime)
        for i in range(len(frame_packets)):
            while frame_packets[i].end_read_dt < most_recent_last_frame_dt:
                new_frame = self.capture_subscribers[frame_packets[i].device.uuid].read(block=True, timeout=timeout)
                
                if new_frame is None:
                    self.logger.warn("failed to read next frame")
                    sleep(0.1)
                
                self.last_frames_datetime[i] = frame_packets[i].end_read_dt
                frame_packets[i] = new_frame
        
        return frame_packets
    
    def empty_queues(self):
        self.logger.info("emptying capture queues ...")
        
        # set empty queue event
        for capture_subscriber in self.capture_subscribers.values():
            capture_subscriber.queue_empty_event.set()
        
        for capture_subscriber in self.capture_subscribers.values():
            while capture_subscriber.output_queue.qsize() > 0:
                
                try:
                    capture_subscriber.output_queue.get(timeout=1)
                except ValueError:
                    self.logger.warning("failed to empty queue")
                    break
        
        # clear empty queue event
        for capture_subscriber in self.capture_subscribers.values():
            capture_subscriber.queue_empty_event.clear()
        
        self.logger.info("queues emptied !")


class MultiInputStreamPublisher:
    """
        Publishes multiple input streams to individual ZMQ sockets.
        
        ! if background is set, the calling process is responsible for calling stop() at termination !
    """
    
    def __init__(
            self, 
            devices: List[Union[AudioDevice, Camera]], 
            host: str = "127.0.0.1", 
            camera_frame_transforms: dict[str, str] = {} # for camera input readers
        ):
        
        self.logger = getLogger(self.__class__.__name__)
        assert len(devices) > 0, "no cameras provided"
        self.capture_publishers = {device.uuid: InputStreamPublisher(device, host, camera_frame_transforms.get(device.uuid, None)) for device in devices}
        
    def stop(self, terminate=False):
        # stop all capture publishers processes and wait for cleanup (unless terminate is set, then terminate immediately)
        self.logger.info("stopping ...")
        
        for capture_publisher in self.capture_publishers.values():
            capture_publisher.stop_process(terminate=terminate)
            
        self.logger.info("stopped !")
        
    def start(self, background: bool = True):
        
        self.logger.info("starting ...")
        
        try:
            # start all capture publishers processes
            for capture_publisher in self.capture_publishers.values():
                capture_publisher.start_process()
        except:
            self.stop(terminate=True)
            raise
        self.logger.info("started !")
        
        if background:
            return
        
        try:
            while True:
                
                # check if any of the processes have stopped and restart if desired
                for capture_publisher in self.capture_publishers.values():
                    
                    if capture_publisher.process is None:
                        raise Exception("has not started")
                    
                    if not capture_publisher.process.is_alive():
                        # TODO: self.restart(k)
                        raise Exception("has stopped")
                
                sleep(0.5)
                
        except KeyboardInterrupt:
            self.logger.info("KeyboardInterrupt ...")
        except:
            raise
        finally:
            self.stop()
