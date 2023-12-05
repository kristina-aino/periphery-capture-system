from zmq.asyncio import Context, Socket
from zmq import SNDMORE, SUBSCRIBE, SUB, PUB, Context
from numpy import ndarray, uint8, ascontiguousarray, frombuffer
from logging import getLogger
from traceback import format_exc

# ----------------------------------------

logger = getLogger(__name__)

# ----------------------------------------

class ZMQPublisher():
    """
        Publishes data to a ZMQ socket.
    """
    
    def __init__(
        self, 
        host_name: str = "127.0.0.1", 
        port=10000):
        
        self.context = Context()
        self.socket = self.context.socket(PUB)
        self.socket.bind(f"tcp://{host_name}:{port}")
        
        self.con_str = f"tcp://{host_name}:{port}"
        
        logger.info(f"ZMQPublisher initialized")
        logger.debug(f"ZMQPublisher bound to {self.con_str}")
        
    def close(self):
        self.socket.close()
        self.context.term()
        logger.info(f"ZMQPublisher stopped")
        logger.debug(f"ZMQPublisher unbound from {self.con_str}")

    def publish(self, image: ndarray[uint8], data: dict):
        assert "image_data" not in data, "Key 'image_data' is reserved for image data"

        data["image_data"] = {
            "dtype": str(image.dtype),
            "shape": image.shape
        }
        
        if not image.flags["C_CONTIGUOUS"]:
            image = ascontiguousarray(image)
        
        self.socket.send_json(data, flags=SNDMORE)
        self.socket.send(image, copy=False, track=False)
        
        logger.debug(f"ZMQPublisher {self.con_str} published data: {data}")

class ZMQSubscriber():
    """
        Subscribes to a ZMQ socket.
    """
    
    def __init__(
        self, 
        host_name: str = "127.0.0.1",
        port=10000):
        
        # ZMQ setup
        self.context = Context()
        self.socket = self.context.socket(SUB)
        self.socket.setsockopt(SUBSCRIBE, b"")
        self.socket.connect(f"tcp://{host_name}:{port}")
        
        logger.debug(f"ZMQSubscriber connected to tcp://{host_name}:{port}")

    def recieve(self) -> tuple[ndarray[uint8], dict]:
        
        if not self.socket.poll(1000):
            logger.warning("No data recieved")
            return None
        
        data = self.socket.recv_json()
        buf_image = self.socket.recv(copy=False, track=False)
        
        logger.debug(f"ZMQSubscriber recieved data: {data}")
        
        image = frombuffer(buf_image, dtype=data["image_data"]["dtype"])
        image = image.reshape(data["image_data"]['shape'])
        
        return image, data