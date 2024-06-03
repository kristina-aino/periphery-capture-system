from abc import ABC, abstractmethod
from typing import Union
from typing_extensions import Annotated
from pydantic import BaseModel, Field, StrictStr, Strict, StrictInt
from dataclasses import dataclass
from numpy import ndarray, uint8, int16
from datetime import datetime
from numpy import ascontiguousarray

StrictNonEmptyStr = Annotated[StrictStr, Field(min_length=1), Strict()]

class Camera(BaseModel):
    uuid: StrictNonEmptyStr # unique identifier for the camera
    id: Annotated[StrictInt, Field(ge=0)] # index of the camera in the system (opencv index)
    publishing_port: Annotated[StrictInt, Field(ge=1025, le=65535)] # port to publish camera data to
    width: Annotated[StrictInt, Field(ge=640, le=3840)]
    height: Annotated[StrictInt, Field(ge=480, le=2160)]
    fps: Annotated[StrictInt, Field(ge=15, le=120)]
    name: StrictNonEmptyStr

class AudioDevice(BaseModel):
    uuid: StrictNonEmptyStr # unique identifier for the audio device
    id: Annotated[StrictInt, Field(ge=0)] # index of the audio device in the system (pyaudio index)
    publishing_port: Annotated[StrictInt, Field(ge=1025, le=65535)] # port to publish audio data to
    type: StrictNonEmptyStr
    sample_rate: Annotated[StrictInt, Field(ge=8000, le=192000)] # sample rate in Hz
    frames_per_buffer: Annotated[StrictInt, Field(ge=1)]
    channels: Annotated[StrictInt, Field(ge=1)]


class VideoParameters(BaseModel):
    save_path: StrictNonEmptyStr # Path to save the videos under save_path/videos
    fps: Annotated[StrictInt, Field(ge=15, le=120)]
    seconds: Annotated[StrictInt, Field(ge=1)] # Number of seconds in output video
    codec: Annotated[StrictStr, Field(min_length=4, max_length=4)] # Codec to use for the video
    output_format: StrictNonEmptyStr

class ImageParameters(BaseModel):
    save_path: StrictNonEmptyStr # Path to save the images under save_path/images
    jpg_quality: Annotated[StrictInt, Field(ge=0, le=100)]
    png_compression: Annotated[StrictInt, Field(ge=0, le=100)]
    output_format: StrictNonEmptyStr

@dataclass
class FramePacket(ABC):
    device: Union[AudioDevice, Camera]
    frames: ndarray
    start_read_dt: datetime
    end_read_dt: datetime
    
    # format data for sending over zero mq
    @abstractmethod
    def dump_zmq(self):
        
        # check if frame is contiguous and convert to contiguous if not
        if not self.frames.flags["C_CONTIGUOUS"]:
            self.frames = ascontiguousarray(self.frames)
        
        # get device type
        if isinstance(self.device, AudioDevice):
            device_type = "audio"
        elif isinstance(self.device, Camera):
            device_type = "camera"
        else:
            raise NotImplementedError("device type not implemented")
        
        return (
            self.frames, 
            {
                "device_type": device_type,
                "device": self.device.model_dump(),
                "frames_data": {
                    "dtype": str(self.frames.dtype),
                    "shape": self.frames.shape
                },
                "start_read_timestamp": self.start_read_dt.timestamp(),
                "end_read_timestamp": self.end_read_dt.timestamp()
            }
        )
    
    # if data is read from zero mq
    @classmethod
    @abstractmethod
    def create(cls, frames: ndarray, data: dict):
        if data["device_type"] == "audio":
            return AudioFramePacket.create(frames, data)
        elif data["device_type"] == "camera":
            return CameraFramePacket.create(frames, data)
        else:
            raise NotImplementedError("device type not implemented")
    
    def __post_init__(self):
        assert isinstance(self.device, (AudioDevice, Camera)), "device must be a valid type"
        assert isinstance(self.frames, ndarray), "frame must be a numpy array"
        assert isinstance(self.start_read_dt, datetime), "start read datetime must be a datetime object"
        assert isinstance(self.end_read_dt, datetime), "end read datetime must be a datetime object"

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