from datetime import datetime
from zmq import SNDMORE, SUBSCRIBE, SUB, PUB, Context, SNDHWM, RCVHWM
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
        
        self.logger_prefix = f"{self.__class__.__name__} :: {host_name}:{port} -"
        
        logger.info(f"{self.logger_prefix} initializing ...")
        
        self.con_str = f"tcp://{host_name}:{port}"
        
        self.context = Context()
        self.socket = self.context.socket(PUB)
        self.socket.setsockopt(SNDHWM, 1)
        self.socket.bind(self.con_str)
        
        logger.info(f"{self.logger_prefix} initialized !")
        
        self.last_start_read_dt = datetime.now()
        
    def is_ok(self):
        return not self.socket.closed and not self.context.closed
        
    def close(self):
        logger.info(f"{self.logger_prefix} :: closeing ...")
        self.socket.close()
        self.context.term()
        logger.info(f"{self.logger_prefix} :: closed !")
        
    def prepare_packet(self, frame_packet: CameraFramePacket) -> (ndarray[uint8], dict):
        frame, data = frame_packet.dump()
        if not frame.flags["C_CONTIGUOUS"]:
            frame = ascontiguousarray(frame)
        return frame, data
        
    def publish(self, frame_packet: CameraFramePacket):
        assert self.is_ok(), f"{self.logger_prefix} is not ok !"
        
        frame, data = self.prepare_packet(frame_packet)
        self.socket.send_json(data, flags=SNDMORE)
        self.socket.send(frame, copy=False, track=False)
        
        # debug the published data
        logger.debug(f"{self.logger_prefix} data: {data}")
        
        # debug the record time
        dt = frame_packet.start_read_dt.timestamp() - self.last_start_read_dt.timestamp()
        logger.debug(f"{self.logger_prefix} frame: {frame_packet.camera.uuid} :: fps: {1/(dt+1e-5)}")
        self.last_start_read_dt = frame_packet.start_read_dt
        
    async def async_publish(self, frame_packet: CameraFramePacket):
        self.publish(frame_packet)

class ZMQSubscriber():
    """
        Subscribes to a single ZMQ socket to collect CameraFramePacket.
    """
    
    def __init__(self, host_name: str, port: int):
        
        self.logger_prefix = f"{self.__class__.__name__} :: {host_name}:{port} -"
        
        logger.info(f"{self.logger_prefix} initializing ...")
        
        self.con_str = f"tcp://{host_name}:{port}"
        
        # ZMQ setup
        self.context = Context()
        self.socket = self.context.socket(SUB)
        self.socket.setsockopt(SUBSCRIBE, b"")
        self.socket.setsockopt(RCVHWM, 1)
        self.socket.connect(self.con_str)
        
        logger.debug(f"{self.logger_prefix} :: initialized !")
        
    def is_ok(self):
        return not self.socket.closed and not self.context.closed
    
    def close(self):
        logger.info(f"{self.logger_prefix} closing ...")
        
        self.socket.close()
        self.context.term()
        
        logger.info(f"{self.logger_prefix} closed !")
    
    def recieve(self) -> CameraFramePacket:
        
        assert self.is_ok(), f"{self.logger_prefix} is not ok !"
        
        if not self.socket.poll(1000):
            logger.warning(f"{self.logger_prefix} no data recieved")
            return None
        
        data = self.socket.recv_json()
        buf_image = self.socket.recv(copy=False, track=False)
        image = frombuffer(buf_image, dtype=data["image_data"]["dtype"])
        image = image.reshape(data["image_data"]['shape'])
        
        # logger.debug(f"{self.con_str} :: ZMQSubscriber recieved data: {data}")
        
        return CameraFramePacket.create(frame=image, data=data)
    
    async def async_recieve(self) -> CameraFramePacket:
        return self.recieve()
