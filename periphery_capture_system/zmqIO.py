import zmq
import importlib
import json

from datetime import datetime
from numpy import frombuffer
from logging import getLogger

from periphery_capture_system import datamodel


class ZMQSender():
    
    def __init__(
        self, 
        host_name: str, 
        port: int,
        send_wait_time_ms: int = 1000,
        response_wait_time_ms: int = 1000):
        
        self.logger = getLogger(f"{self.__class__.__name__}@{host_name}:{port}")
        
        self.send_wait_time_ms = send_wait_time_ms
        self.response_wait_time_ms = response_wait_time_ms
        
        self.logger.info("initializing ...")
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.SNDHWM, 1)
        self.socket.bind(f"tcp://{host_name}:{port}")
        self.logger.info("initialized !")
    
    def is_ok(self):
        return not self.socket.closed and not self.context.closed
    
    def close(self):
        self.logger.info("closeing ...")
        self.socket.close()
        self.context.term()
        self.logger.info("closed !")
    
    def send(self, packet: datamodel.FramePacket):
        
        if not self.is_ok():
            self.logger.error("publisher is not ok !")
            raise Exception("publisher is not ok !")
        
        self.logger.debug("sending data ...")
        packet_dump = packet.dump()
        frame = packet_dump["frame"]
        data = packet_dump["data"]
        
        try:
            self.socket.send_json(data, zmq.SNDMORE | zmq.NOBLOCK)
            self.socket.send(frame, flags=zmq.NOBLOCK, copy=False, track=False)
        except zmq.error.Again:
            self.logger.warning("could not send data")
            return
        
        if not self.socket.poll(self.response_wait_time_ms):
            self.logger.warning("timeout waiting for reciever response")
            return
        
        return self.socket.recv()

class ZMQReciever():
    """
        Subscribes to a single ZMQ socket to collect Packets.
    """
    
    def __init__(
        self, 
        host_name: str, 
        port: int,
        recieve_wait_time_ms: int = 1000):
        
        self.logger = getLogger(f"{self.__class__.__name__}@{host_name}:{port}")
        
        self.recieve_wait_time_ms = recieve_wait_time_ms
        
        self.logger.info("initializing ...")
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.setsockopt(zmq.RCVHWM, 1)
        self.socket.connect(f"tcp://{host_name}:{port}")
        self.logger.debug("finitialized !")
        
    def is_ok(self):
        return not self.socket.closed and not self.context.closed
    
    def close(self):
        self.logger.info("closing ...")
        self.socket.close()
        self.context.term()
        self.logger.info("closed !")
    
    def recieve(self) -> datamodel.FramePacket:
        
        if not self.is_ok():
            self.logger.error("reciever is not ok !")
            raise Exception("reciever is not ok !")
        
        if not self.socket.poll(self.recieve_wait_time_ms):
            self.logger.warning("timeout waiting for sender message")
            return None
        
        data = self.socket.recv_json(flags=zmq.NOBLOCK)
        frame = self.socket.recv(flags=zmq.NOBLOCK, copy=False, track=False)
        
        self.logger.debug("data recieved ...")
        self.socket.send_string("ACK")
        
        # format frame
        frame = frombuffer(frame, dtype=data["frame"]["dtype"])
        frame = frame.reshape(data["frame"]["shape"])
        
        # format device
        device_class = getattr(datamodel, data["device"]["type"])
        
        return datamodel.FramePacket(
            device=device_class(**data["device"]["parameters"]),
            frame=frame,
            start_read_dt=datetime.fromtimestamp(data["start_read_timestamp"]),
            end_read_dt=datetime.fromtimestamp(data["end_read_timestamp"])
        )
