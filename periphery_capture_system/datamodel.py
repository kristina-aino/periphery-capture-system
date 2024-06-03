# from abc import ABC, abstractmethod
from typing import Union, Any
from typing_extensions import Annotated
from pydantic import BaseModel, field_validator, Field, StrictStr, Strict, StrictInt
from dataclasses import dataclass
from numpy import ndarray, uint8, int16
from datetime import datetime
from numpy import ascontiguousarray

# ---------- TYPE DEFINITIONS ----------

StrictNonEmptyStr = Annotated[StrictStr, Field(min_length=1), Strict()]
PortNumber = Annotated[StrictInt, Field(ge=1025, le=65535)]

# ---------- BASE CLASSES ----------

class PeripheryDevice(BaseModel):
    uuid: StrictNonEmptyStr
    description: StrictNonEmptyStr
    publishing_port: PortNumber

class MediaSaveParameters(BaseModel):
    save_path: StrictNonEmptyStr # Path to save the media under save_path/media
    output_format: StrictNonEmptyStr

class FramePacket(BaseModel):
    device: PeripheryDevice
    frame: Any
    start_read_dt: datetime
    end_read_dt: datetime
    
    @field_validator("frame")
    def validate_frame(cls, value):
        if not isinstance(value, ndarray):
            raise TypeError("frame must be a numpy array")
        return value
    
    def dump(self):
        
        # check if frame is contiguous and convert to contiguous if not
        if not self.frame.flags["C_CONTIGUOUS"]:
            self.frame = ascontiguousarray(self.frame)
        
        return {
            "frame": self.frame, 
            "data": {
                "start_read_timestamp": self.start_read_dt.timestamp(),
                "end_read_timestamp": self.end_read_dt.timestamp(),
                "frame": {
                    "shape": list(self.frame.shape),
                    "dtype": str(self.frame.dtype)
                },
                "device": {
                    "type": self.device.__class__.__name__,
                    "parameters": self.device.model_dump(),
                }
            }
        }
    
    # # if data is read from zero mq
    # @classmethod
    # @abstractmethod
    # def create(cls, frames: ndarray, data: dict):
    #     if data["device_type"] == "audio":
    #         return AudioFramePacket.create(frames, data)
    #     elif data["device_type"] == "camera":
    #         return CameraFramePacket.create(frames, data)
    #     else:
    #         raise NotImplementedError("device type not implemented")

# ---------- DATA CLASSES ----------

class Camera(PeripheryDevice):
    # uuid: StrictNonEmptyStr # unique identifier for the camera
    id: Annotated[StrictInt, Field(ge=0)] # index of the camera in the system (opencv index)
    width: Annotated[StrictInt, Field(ge=640, le=3840)]
    height: Annotated[StrictInt, Field(ge=480, le=2160)]
    fps: Annotated[StrictInt, Field(ge=15, le=120)]
    # name: StrictNonEmptyStr

class AudioDevice(PeripheryDevice):
    # uuid: StrictNonEmptyStr # unique identifier for the audio device
    id: Annotated[StrictInt, Field(ge=0)] # index of the audio device in the system (pyaudio index)
    type: StrictNonEmptyStr
    sample_rate: Annotated[StrictInt, Field(ge=8000, le=192000)] # sample rate in Hz
    frames_per_buffer: Annotated[StrictInt, Field(ge=1)]
    channels: Annotated[StrictInt, Field(ge=1)]

class VideoParameters(MediaSaveParameters):
    fps: Annotated[StrictInt, Field(ge=15, le=120)]
    seconds: Annotated[StrictInt, Field(ge=1)] # Number of seconds in output video
    codec: Annotated[StrictStr, Field(min_length=4, max_length=4)] # Codec to use for the video

class ImageParameters(MediaSaveParameters):
    jpg_quality: Annotated[StrictInt, Field(ge=0, le=100)]
    png_compression: Annotated[StrictInt, Field(ge=0, le=100)]

@dataclass
class AudioFramePacket(FramePacket):
    device: AudioDevice
    
    def dump_zmq(self):
        return super().dump_zmq()
    
    @classmethod
    def create(cls, frames: ndarray[int16], data: dict):
        return cls(
            device=AudioDevice(**data["device"]),
            frames=frames,
            start_read_dt=datetime.fromtimestamp(data["start_read_timestamp"]),
            end_read_dt=datetime.fromtimestamp(data["end_read_timestamp"]))

@dataclass
class CameraFramePacket(FramePacket):
    device: Camera
    
    def dump_zmq(self):
        return super().dump_zmq()
    
    @classmethod
    def create(cls, frames: ndarray[uint8], data: dict):
        return cls(
            device=Camera(**data["device"]),
            frames=frames,
            start_read_dt=datetime.fromtimestamp(data["start_read_timestamp"]),
            end_read_dt=datetime.fromtimestamp(data["end_read_timestamp"]))