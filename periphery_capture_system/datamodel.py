# from abc import ABC, abstractmethod
from enum import Enum
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
class VideoFormatType(Enum):
    MP4 = "MP4"
class VideoCodecType(Enum):
    MP4V = "MP4V"
class ImageFormatType(Enum):
    JPG = "JPG"
    PNG = "PNG"

# ---------- BASE CLASSES ----------

class PeripheryDevice(BaseModel):
    device_id: StrictNonEmptyStr # the ffmpeg unique hardware identifer, under windows its pnp for video and cm for audio devices
    name: StrictNonEmptyStr
    device_type: Union[StrictNonEmptyStr, None]

class MediaSaveParameters(BaseModel):
    save_path: StrictNonEmptyStr # Path to save the media under save_path/media

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

# ---------- DEVICE CLASSES ----------

class CameraDevice(PeripheryDevice):
    width: Annotated[StrictInt, Field(ge=640, le=3840)]
    height: Annotated[StrictInt, Field(ge=480, le=2160)]
    fps: Annotated[StrictInt, Field(ge=15, le=120)]

class AudioDevice(PeripheryDevice):
    sample_rate: Annotated[StrictInt, Field(ge=8000, le=192000)] # sample rate in Hz
    bit_rate: Annotated[StrictInt, Field(ge=1)]
    channels: Annotated[StrictInt, Field(ge=1)]

class VideoParameters(MediaSaveParameters):
    video_output_format: VideoFormatType
    fps: Annotated[StrictInt, Field(ge=15, le=120)]
    seconds: Annotated[StrictInt, Field(ge=1)] # Number of seconds in output video
    codec: VideoCodecType

class ImageParameters(MediaSaveParameters):
    image_output_format: ImageFormatType
    jpg_quality: Annotated[StrictInt, Field(ge=0, le=100)]
    png_compression: Annotated[StrictInt, Field(ge=0, le=100)]
