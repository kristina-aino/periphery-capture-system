from datetime import datetime
from zmq import SNDMORE, SUBSCRIBE, SUB, PUB, Context, SNDHWM, RCVHWM
from numpy import frombuffer
from logging import getLogger
from typing import Union

from .datamodel import FramePacket

# ------------------- ZMQ IO ------------------- #

class ZMQPublisher():
    """
        Publishes packets to a single ZMQ socket.
    """
    
    def __init__(self, host_name: str, port: int):
        
        self.logger = getLogger(self.__class__.__name__)
        
        self.logger.info("initializing ...")
        
        self.context = Context()
        self.socket = self.context.socket(PUB)
        self.socket.setsockopt(SNDHWM, 1)
        self.socket.bind(f"tcp://{host_name}:{port}")
        
        self.logger.info("initialized !")
        
        self.last_start_read_dt = datetime.now()
        
    def is_ok(self):
        return not self.socket.closed and not self.context.closed
        
    def close(self):
        self.logger.info("closeing ...")
        self.socket.close()
        self.context.term()
        self.logger.info("closed !")
        
    def publish(self, packet: FramePacket):
        assert self.is_ok(), f"{self.logger_prefix} is not ok !"
        
        frame, data = packet.dump_zmq()
        self.socket.send_json(data, flags=SNDMORE)
        self.socket.send(frame, copy=False, track=False)
        
        # # debug the record time
        # dt = packet.start_read_dt.timestamp() - self.last_start_read_dt.timestamp()
        # self.logger.debug(f"frame: {packet.device.uuid} :: fps: {1/(dt+1e-5)}")
        # self.last_start_read_dt = packet.start_read_dt

class ZMQSubscriber():
    """
        Subscribes to a single ZMQ socket to collect Packets.
    """
    
    def __init__(self, host_name: str, port: int):
        
        self.logger = getLogger(f"{self.__class__.__name__} - {host_name}:{port}")
        
        self.logger.info("initializing ...")
        
        # ZMQ setup
        self.context = Context()
        self.socket = self.context.socket(SUB)
        self.socket.setsockopt(SUBSCRIBE, b"")
        self.socket.setsockopt(RCVHWM, 1)
        self.socket.connect(f"tcp://{host_name}:{port}")
        
        self.logger.debug("finitialized !")
        
    def is_ok(self):
        return not self.socket.closed and not self.context.closed
    
    def close(self):
        self.logger.info("closing ...")
        
        self.socket.close()
        self.context.term()
        
        self.logger.info("closed !")
    
    def recieve(self) -> FramePacket:
        
        assert self.is_ok(), f"{self.logger_prefix} is not ok !"
        
        if not self.socket.poll(1000):
            self.logger.warning("no data recieved")
            return None
        
        data = self.socket.recv_json()
        buf_frames = self.socket.recv(copy=False, track=False)
        frames = frombuffer(buf_frames, dtype=data["frames_data"]["dtype"])
        frames = frames.reshape(data["frames_data"]['shape'])
        
        self.logger.debug(f"recieved frame: {data['device']['uuid']} - output shape: {frames.shape}")
        
        fp = FramePacket.create(frames=frames, data=data)
        return fp
