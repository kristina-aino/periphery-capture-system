import zmq
import importlib
import json

from datetime import datetime
from numpy import frombuffer
from logging import getLogger

from periphery_capture_system import datamodel


class ZMQSender():
    
    def __init__(self, host: str, port: int, q_size: int = 1, send_wait_time_ms: int = 1000, response_wait_time_ms: int = 1000):
        
        self.logger = getLogger(f"{self.__class__.__name__}@{host}:{port}")
        
        self.host = host
        self.port = port
        self.q_size = q_size
        self.send_wait_time_ms = send_wait_time_ms
        self.response_wait_time_ms = response_wait_time_ms
        
        self.context = None
        self.socket = None
    
    def is_active(self):
        return self.context is not None
    
    def start(self):
        self.logger.info("starting ...")
        
        if self.is_active():
            self.logger.warning("sender is already started, restarting ...")
            self.stop()
        
        try:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.REQ)
            self.socket.setsockopt(zmq.SNDHWM, self.q_size)
            self.socket.bind(f"tcp://{self.host}:{self.port}")
        except Exception as e:
            self.stop()
            raise e
        
        self.logger.info("started !")
    
    def stop(self):
        self.logger.info("stoping ...")
        if self.socket is not None:
            self.socket.close()
        if self.context is not None:
            self.context.term()
        self.context = None
        self.socket = None
        self.logger.info("stoped !")
    
    def send(self, packet: datamodel.FramePacket):
        
        if not self.is_active():
            raise Exception("trying to send data without starting the sender !")
        
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
    
    def __init__(self, host: str, port: int, q_size: int = 1, recieve_wait_time_ms: int = 1000):
        
        self.logger = getLogger(f"{self.__class__.__name__}@{host}:{port}")
        
        self.host = host
        self.port = port
        self.q_size = q_size
        self.recieve_wait_time_ms = recieve_wait_time_ms
        
        self.context = None
        self.socket = None
        
    def is_active(self):
        return self.context is not None
    
    def start(self):
        self.logger.info("initializing ...")
        
        if self.is_active():
            self.logger.warning("reciever is already started, restarting ...")
            self.stop()
        
        try:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.REP)
            self.socket.setsockopt(zmq.RCVHWM, self.q_size)
            self.socket.connect(f"tcp://{self.host}:{self.port}")
        except Exception as e:
            self.stop()
            raise e
        
        self.logger.info("initialized !")
    
    def stop(self):
        self.logger.info("stopping ...")
        
        if self.socket is not None:
            self.socket.close()
        if self.context is not None:
            self.context.term()
        self.context = None
        self.socket = None
        
        self.logger.info("stopped !")
    
    def recieve(self) -> datamodel.FramePacket:
        
        if not self.is_active():
            raise Exception("trying to recieve data without starting the reciever !")
        
        try:
            
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
            device = device_class(**data["device"]["parameters"])
            
            # extract timestamp
            start_read_dt = datetime.fromtimestamp(data["start_read_timestamp"])
            end_read_dt = datetime.fromtimestamp(data["end_read_timestamp"])
            
        except Exception as e:
            self.stop()
            raise e
        
        return datamodel.FramePacket(
            device=device,
            frame=frame,
            start_read_dt=start_read_dt,
            end_read_dt=end_read_dt
        )
