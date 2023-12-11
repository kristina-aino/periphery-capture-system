from zmq.asyncio import Context
from zmq import SNDMORE, SUBSCRIBE, SUB, PUB, Context
from numpy import ascontiguousarray, frombuffer, ndarray, uint8
from logging import getLogger

from .datamodel import CameraFramePacket

# ------------------- Logging ------------------- #

logger = getLogger(__name__)

# ------------------- ZMQ IO ------------------- #

class ZMQPublisher():
    """
        Publishes CameraFramePacket to a single ZMQ socket.
    """
    
    def __init__(self, host_name: str, port: int):
        
        self.con_str = f"tcp://{host_name}:{port}"
        
        self.context = Context()
        self.socket = self.context.socket(PUB)
        self.socket.bind(self.con_str)
        
        logger.info(f"ZMQPublisher initialized")
        logger.debug(f"ZMQPublisher bound to {self.con_str}")
        
    def close(self):
        self.socket.close()
        self.context.term()
        logger.info(f"ZMQPublisher {self.con_str} stopped and unbound")
        
    def prepare_packet(self, frame_packet: CameraFramePacket) -> (ndarray[uint8], dict):        
        frame, data = frame_packet.dump()
        if not frame.flags["C_CONTIGUOUS"]:
            frame = ascontiguousarray(frame)
        return frame, data
        
    def publish(self, frame_packet: CameraFramePacket):
        assert not self.socket.closed and not self.context.closed, f"ZMQPublisher {self.con_str} is not ok"
        
        frame, data = self.prepare_packet(frame_packet)
        self.socket.send_json(data, flags=SNDMORE)
        self.socket.send(frame, copy=False, track=False)
        logger.debug(f"ZMQPublisher {self.con_str} published data: {data}")
        
    async def async_publish(self, frame_packet: CameraFramePacket):
        self.publish(frame_packet)    

class ZMQSubscriber():
    """
        Subscribes to a single ZMQ socket to collect CameraFramePacket.
    """
    
    def __init__(self, host_name: str, port: int):
        
        self.con_str = f"tcp://{host_name}:{port}"
        
        # ZMQ setup
        self.context = Context()
        self.socket = self.context.socket(SUB)
        self.socket.setsockopt(SUBSCRIBE, b"")
        self.socket.connect(self.con_str)
        
        logger.debug(f"ZMQSubscriber connected to {self.con_str}")
        
    def close(self):
        self.socket.close()
        self.context.term()
        logger.info(f"ZMQSubscriber stopped")
        logger.debug(f"ZMQSubscriber unbound from {self.con_str}")

    def recieve(self) -> CameraFramePacket:
        
        if not self.socket.poll(1000):
            logger.warning(f"{self.con_str} :: No data recieved")
            return None
        
        data = self.socket.recv_json()
        buf_image = self.socket.recv(copy=False, track=False)
        image = frombuffer(buf_image, dtype=data["image_data"]["dtype"])
        image = image.reshape(data["image_data"]['shape'])
        
        logger.debug(f"ZMQSubscriber {self.con_str} recieved data: {data}")
        
        return CameraFramePacket.create(frame=image, data=data)
    
    async def async_recieve(self) -> CameraFramePacket:
        return self.recieve()