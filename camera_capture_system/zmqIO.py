import time
import zmq
from numpy import ndarray, uint8, ascontiguousarray, frombuffer
from logging import warning, error
from threading import Event
from traceback import format_exc


class ZMQPublisher():
    """
        Publishes data to a ZMQ socket.
    """
    
    def __init__(
        self, 
        host_name: str = "127.0.0.1", 
        port=10000):
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://{host_name}:{port}")

    def publish(self, image: ndarray[uint8], data: dict):
        assert "image_data" not in data, "Key 'image_data' is reserved for image data"
        
        data["image_data"] = {
            "dtype": str(image.dtype),
            "shape": image.shape
        }
        
        if not image.flags["C_CONTIGUOUS"]:
            image = ascontiguousarray(image)
        
        self.socket.send_json(data, flags=zmq.SNDMORE)
        self.socket.send(image, flags=0, copy=False, track=False)

class ZMQSubscriber():
    """
        Subscribes to a ZMQ socket.
    """
    
    def __init__(
        self, 
        host_name: str = "127.0.0.1",
        port=10000):
                
        # ZMQ setup
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.socket.connect(f"tcp://{host_name}:{port}")

    def recieve(self):
    
        try:
            data = self.socket.recv_json()
            buf_image = self.socket.recv(copy=False, track=False)
            
            image = frombuffer(buf_image, dtype=data["image_data"]["dtype"])
            image = image.reshape(data["image_data"]['shape'])
        
        except:
            error(format_exc())
        finally:
            self.socket.close()
            self.context.term()