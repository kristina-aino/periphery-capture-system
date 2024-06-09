import time

from typing import List
from time import sleep
from logging import getLogger
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process, Event
from multiprocessing import TimeoutError as ProcessTimeoutError

from .datamodel import FramePacket, PeripheryDevice, CameraDevice, AudioDevice, PortNumber
from .deviceIO import FFMPEGReader, CameraDeviceReader, AudioDeviceReader
from .zmqIO import ZMQSender, ZMQReceiver

# ------------- SINGLE STREAM CLASSES -------------

class InputStreamSender:
    def __init__(self, device: PeripheryDevice, port: int, host: str = "127.0.0.1", invalid_frame_timeout: float = 1.):
        self.logger = getLogger(f"{self.__class__.__name__}:{device.name}")
        
        self.device = device
        self.host = host
        self.port = port
        
        # timeouts
        self.invalid_frame_timeout = invalid_frame_timeout
        
        # for multiprocessing
        self.stop_event = Event()
        self.process = None
    
    def is_active(self): return self.process is not None
    
    def start_process(self):
        
        self.logger.info("starting ...")
        
        assert not self.is_active(), "trying to start a process that has already started, restarting ..."
        
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
        
        # crteate device reader and zmq sender
        zmq_sender = ZMQSender(host=self.host, port=self.port)
        if isinstance(self.device, CameraDevice):
            device_reader = CameraDeviceReader(self.device)
        elif isinstance(self.device, AudioDevice):
            device_reader = AudioDeviceReader(self.device)
        else:
            raise ValueError("device type not supported")
        
        try:
            zmq_sender.start()
            device_reader.start()
            
            while not self.stop_event.is_set():
                
                dt = time.perf_counter()
                
                # read frame
                frame_packet = device_reader.read()
                if frame_packet is None:
                    sleep(self.invalid_frame_timeout)
                    continue
                
                # send frame
                zmq_sender.send(frame_packet)
                
                
                send_time = (time.perf_counter() - dt)
                if send_time > 0:
                    self.logger.debug(f"frame read and sent with fps {1 / send_time}")
                
        except Exception as e:
            raise e
        finally:
            zmq_sender.stop()
            device_reader.stop()

class InputStreamReceiver:
    
    def __init__(self, port: int, host: str = "127.0.0.1"):
        self.logger = getLogger(f"{self.__class__.__name__}" )
        self.zmq_receiver = ZMQReceiver(host=host, port=port)
    
    def start(self):
        self.logger.info("starting ...")
        self.zmq_receiver.start()
        self.logger.info("started !")
        
    def stop(self):
        self.logger.info("stopping ...")
        self.zmq_receiver.stop()
        self.logger.info("stopped !")
        
    def read(self):
        try:
            frame_packet = self.zmq_receiver.receive()
        except Exception as e:
            self.stop()
            raise e
        
        return frame_packet

# ------------- MULTI STREAM CLASSES -------------

class MultiInputStreamSender:
    
    def __init__(self, devices: List[PeripheryDevice], ports: List[int], host: str = "127.0.0.1"):
        self.logger = getLogger(self.__class__.__name__)
        
        assert len(devices) == len(ports), "number of devices and ports must be equal"
        
        self.input_sender = [InputStreamSender(device, port, host) for device, port in zip(devices, ports)]
        
        self.logger.info(f"multi input stream sender with {len(self.input_sender)} senders")
        
    def stop_processes(self, timeout: float = 1):
        for sub in self.input_sender:
            sub.stop_process(timeout=timeout)
        
    def start_processes(self):
        for sub in self.input_sender:
            sub.start_process()

class MultiInputStreamReceiver:
    
    def __init__(self, ports: List[int], host: str = "127.0.0.1"):
        self.logger = getLogger(self.__class__.__name__)
        self.capture_reciever = [InputStreamReceiver(port, host) for port in ports]
        
        self.executor = ThreadPoolExecutor(max_workers=len(self.capture_reciever))
        
        self.logger.info(f"multi input stream reciever with {len(self.capture_reciever)} recievers")
        
    def start(self):
        for rec in self.capture_reciever:
            rec.start()
        
    def stop(self):
        for rec in self.capture_reciever:
            rec.stop()
        
    def read(self):
        futures = [self.executor.submit(rec.read) for rec in self.capture_reciever]
        frames = [future.result() for future in futures]
        if any([frame is None for frame in frames]):
            return None
        return frames

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
