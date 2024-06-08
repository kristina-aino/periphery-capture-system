from typing import Union
from time import sleep
from logging import getLogger
from typing import List
from multiprocessing import Process, Event, Manager
from multiprocessing import TimeoutError as ProcessTimeoutError
from queue import Empty as QueueEmpty
from queue import Full as QueueFull

from .datamodel import FramePacket, PeripheryDevice, CameraDevice, AudioDevice, PortNumber
from .deviceIO import FFMPEGReader, CameraDeviceReader, AudioDeviceReader
from .zmqIO import ZMQSender, ZMQReciever


# ------------- Subscribers -------------

class InputStreamSender:
    def __init__(self, device_reader: FFMPEGReader, zmq_sender: ZMQSender, invalid_frame_timeout: float = 1, failed_frame_send_timeout: float = 1):
        self.logger = getLogger(f"{self.__class__.__name__}")
        
        self.device_reader = device_reader
        self.zmq_sender = zmq_sender
        
        # timeouts
        self.invalid_frame_timeout = invalid_frame_timeout
        self.failed_frame_send_timeout = failed_frame_send_timeout
        
        # for multiprocessing
        self.stop_event = Event()
        self.process = None
    
    def is_active(self): return self.process is not None
    
    def start_process(self):
        
        self.logger.info("starting ...")
        
        if self.is_active():
            self.logger.warning("trying to start a process that has already started, restarting ...")
            self.stop_process()
        
        self.stop_event.clear()
        self.process = Process(target=self.run_)
        self.process.start()
        
        self.logger.info("started !")
        
    def stop_process(self, timeout=1):
        
        self.logger.info("stopping...")
        
        self.stop_event.set()
        
        if self.process is None: return
        
        try:
            self.process.join(timeout=timeout)
        except ProcessTimeoutError:
            self.logger.warning("process join timeout, terminating ...")
            self.process.terminate()
        
        self.process = None
        
        self.logger.info("stopped !")
        
    def run_(self):
        
        try:
            
            self.zmq_sender.start()
            self.device_reader.start()
            
            while not self.stop_event.is_set():
                
                # read frame
                frame_packet = self.device_reader.read()
                if frame_packet is None:
                    sleep(self.invalid_frame_timeout)
                    continue
                
                # send frame
                ret = self.zmq_sender.send(frame_packet)
                if ret is None:
                    sleep(self.failed_frame_send_timeout)
                    continue
        
        except Exception as e:
            raise e
        finally:
            self.zmq_sender.stop()
            self.device_reader.stop()

class InputStreamReciever:
    
    def __init__(self, zmq_reciever: ZMQReciever, read_write_timeout: int = 1, failed_frame_recieve_timeout: int = 1):
        self.logger = getLogger(f"{self.__class__.__name__}" )
        
        self.zmq_reciever = zmq_reciever
        
        # timeouts
        self.failed_frame_recieve_timeout = failed_frame_recieve_timeout
        self.read_write_timeout = read_write_timeout
        
        # for multiprocessing
        self.stop_event = Event()
        self.process = None
        self.io_manager = Manager()
        # todo add multiprocessing transfere from run_ to read
    
    def is_active(self): return self.process is not None
    
    def start_process(self):
        
        self.logger.info("starting ...")
        
        if self.is_active():
            self.logger.warning("trying to start a process that has already started, restarting ...")
            self.stop_process()
        
        self.stop_event.clear()
        self.process = Process(target=self.run_)
        self.process.start()
        
        self.logger.info("started !")
        
    def stop_process(self, timeout: int = 1):
        
        self.logger.info("stopping ...")
        
        self.stop_event.set()
        
        if self.process is None: return
        
        try:
            self.process.join(timeout=timeout)
        except ProcessTimeoutError:
            self.logger.warning("process join timeout, terminating ...")
            self.process.terminate()
        
        self.process = None
        
        self.logger.info("stopped !")
        
    def run_(self):
        
        try:
            
            self.zmq_reciever.start()
            
            while not self.stop_event.is_set():
                
                # read frame
                frame_packet = self.zmq_reciever.recieve()
                
                with self.io_condition:
                    self.active_frame_packet = frame_packet
                    self.io_condition.notify()
                
        except Exception as e:
            raise e
        finally:
            self.zmq_reciever.stop()
        
    def read(self):
        with self.io_condition:
            if not self.io_condition.wait(timeout=self.read_write_timeout):
                self.logger.warning("read timeout")
                return None
            return self.active_frame_packet


# class MultiInputStreamSubscriber:
    
#     def __init__(self, devices: List[Union[Camera, AudioDevice]], q_size: int, host: str = "127.0.0.1"):
#         self.logger = getLogger(self.__class__.__name__)
#         self.capture_subscribers = {device.uuid: InputStreamSubscriber(device, q_size, host) for device in devices}
#         self.last_frames_datetime = None
        
#     def stop(self, terminate : bool = True):
#         self.logger.info("starting ...")
        
#         # stop all capture subscribers processes and wait for cleanup
#         for capture_subscriber in self.capture_subscribers.values():
#             capture_subscriber.stop_process(terminate=terminate)
        
#         self.logger.info("stopped !")
        
#     def start(self):
#         self.logger.info("starting ...")
        
#         # start reading from all cameras
#         for capture_subscriber in self.capture_subscribers.values():
#             capture_subscriber.start_process()
        
#         self.logger.info("started !")
        
#     def read(self, block: bool = False, timeout: float = 1, synchronous_read: bool = False) -> Union[List[FramePacket], None]:
        
#         # read from all camera subseiber
#         frame_packets = [self.capture_subscribers[k].read(block=block, timeout=timeout) for k in self.capture_subscribers]
        
#         self.logger.debug(f"valid frame packets: {[f is not None for f in frame_packets]}")
        
#         # return if any packets are None
#         for packet in frame_packets:
#             if packet is None:
#                 return None
        
#         if not synchronous_read:
#             return frame_packets
        
#         # syncronize frames
#         # compute last frames datetime on first read
#         if self.last_frames_datetime is None:
#             self.last_frames_datetime = [*map(lambda a: a.end_read_dt, frame_packets)]
#             return frame_packets
        
#         # read frames until all datetimes line up as accuratl as possible
#         most_recent_last_frame_dt = max(self.last_frames_datetime)
#         for i in range(len(frame_packets)):
#             while frame_packets[i].end_read_dt < most_recent_last_frame_dt:
#                 new_frame = self.capture_subscribers[frame_packets[i].device.uuid].read(block=True, timeout=timeout)
                
#                 if new_frame is None:
#                     self.logger.warn("failed to read next frame")
#                     sleep(0.1)
                
#                 self.last_frames_datetime[i] = frame_packets[i].end_read_dt
#                 frame_packets[i] = new_frame
        
#         return frame_packets
    
#     def empty_queues(self):
#         self.logger.info("emptying capture queues ...")
        
#         # set empty queue event
#         for capture_subscriber in self.capture_subscribers.values():
#             capture_subscriber.queue_empty_event.set()
        
#         for capture_subscriber in self.capture_subscribers.values():
#             while capture_subscriber.output_queue.qsize() > 0:
                
#                 try:
#                     capture_subscriber.output_queue.get(timeout=1)
#                 except ValueError:
#                     self.logger.warning("failed to empty queue")
#                     break
        
#         # clear empty queue event
#         for capture_subscriber in self.capture_subscribers.values():
#             capture_subscriber.queue_empty_event.clear()
        
#         self.logger.info("queues emptied !")


# class MultiInputStreamPublisher:
#     """
#         Publishes multiple input streams to individual ZMQ sockets.
        
#         ! if background is set, the calling process is responsible for calling stop() at termination !
#     """
    
#     def __init__(
#             self, 
#             devices: List[Union[AudioDevice, Camera]], 
#             host: str = "127.0.0.1", 
#             camera_frame_transforms: dict[str, str] = {} # for camera input readers
#         ):
        
#         self.logger = getLogger(self.__class__.__name__)
#         assert len(devices) > 0, "no cameras provided"
#         self.capture_publishers = {device.uuid: InputStreamPublisher(device, host, camera_frame_transforms.get(device.uuid, None)) for device in devices}
        
#     def stop(self, terminate=False):
#         # stop all capture publishers processes and wait for cleanup (unless terminate is set, then terminate immediately)
#         self.logger.info("stopping ...")
        
#         for capture_publisher in self.capture_publishers.values():
#             capture_publisher.stop_process(terminate=terminate)
            
#         self.logger.info("stopped !")
        
#     def start(self, background: bool = True):
        
#         self.logger.info("starting ...")
        
#         try:
#             # start all capture publishers processes
#             for capture_publisher in self.capture_publishers.values():
#                 capture_publisher.start_process()
#         except:
#             self.stop(terminate=True)
#             raise
#         self.logger.info("started !")
        
#         if background:
#             return
        
#         try:
#             while True:
                
#                 # check if any of the processes have stopped and restart if desired
#                 for capture_publisher in self.capture_publishers.values():
                    
#                     if capture_publisher.process is None:
#                         raise Exception("has not started")
                    
#                     if not capture_publisher.process.is_alive():
#                         # TODO: self.restart(k)
#                         raise Exception("has stopped")
                
#                 sleep(0.5)
                
#         except KeyboardInterrupt:
#             self.logger.info("KeyboardInterrupt ...")
#         except:
#             raise
#         finally:
#             self.stop()
