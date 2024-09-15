import av
import re
import concurrent.futures as concurrent_futures
import subprocess

# from capture_devices import devices
from json import dump as json_dump
from json import load as json_load
from typing import List
from abc import ABC, abstractmethod
from logging import getLogger
from logging import getLogger
from datetime import datetime
from traceback import format_exc

from .datamodel import FramePacket
from .datamodel import PeripheryDevice, CameraDevice, AudioDevice

# ------------------- DEVICE UTILS ------------------- #

def get_all_devices_ffmpeg(os: str = "windows"):
    """
        - load all devices from ffmpeg stdout
        - remove prefixes and suffixes
        - concat pnp and cm id's, names and types
    """
    
    if os != "windows":
        raise NotImplementedError("Only windows (dshow) is supported for now ...")
    
    # Get list of input devices
    devices = subprocess.run(["ffmpeg", "-sources", "dshow"], capture_output=True, text=True).stdout
    
    names = [a[1:-1] for a in re.findall(r"\[.*\]", devices)]
    device_ids = [f"@{a[1:-2]}" for a in re.findall(r"\@.*\[", devices)]
    device_types = [a[3:-1] for a in re.findall(r"\].*\(.*.\)", devices)]
    
    return [PeripheryDevice(device_id=device_id, name=name, device_type=device_type) for name, device_id, device_type in zip(names, device_ids, device_types)]

def save_periphery_devices_to_config(devices: List[PeripheryDevice], config_file: str = "./raw_devices.json"):
    with open(config_file, "w") as f:
        json_dump([device.model_dump() for device in devices], f)

def load_all_devices_from_config(device_type: str, config_file: str = "./configs/devices.json") -> List[PeripheryDevice]:
    with open(config_file, "r") as f:
        devices = json_load(f)
    
    video_devices = [device for device in devices if device["device_type"] == "video"]
    audio_devices = [device for device in devices if device["device_type"] == "audio"]
    
    if device_type == "video":
        return [CameraDevice(**device) for device in video_devices]
    elif device_type == "audio":
        return [AudioDevice(**device) for device in audio_devices]
    else:
        raise ValueError("device_type must be either 'video' or 'audio' ...")

# ------------------- BASE CLASS ------------------- #

class FFMPEGReader(ABC):
    def __init__(self, device: PeripheryDevice, logger_name: str):
        self.logger = getLogger(logger_name)
        
        assert isinstance(device, PeripheryDevice), f"device must be an instance of PeripheryDevice, not {type(device)} ..."
        
        self.device = device
        self.container = None
        self.stream = None
    
    def is_active(self):
        return self.container is not None
    
    def stop(self):
        self.logger.info("Stopping ...")
        
        if self.container is not None:
            self.container.close()
            self.container = None
        self.stream = None
        
        self.logger.info("stopped!")
    
    @abstractmethod
    def start(self, file_string: str, options: dict, format: str = "dshow"):
        
        self.logger.info(f"Starting ...")
        
        assert not self.is_active(), f"Trying to start a reader that has already been started ..."
    
        # set container
        self.container = av.open(file=file_string, format='dshow', options=options)
        
        self.logger.debug(f"Open Container with options: {options}")
        
        # set stream (audio or video)
        if self.device.device_type == "audio":
            self.stream = self.container.streams.audio[0]
        elif self.device.device_type == "video":
            self.stream = self.container.streams.video[0]
        else:
            raise Exception("No audio or video stream found ...")
        
        self.logger.info(f"started !")
    
    def read(self, timeout: float = 1):
        
        if not self.is_active():
            self.logger.warning("Trying to read from a reader that is not active ...")
            return None
        
        start_read_dt = datetime.now()
        
        with concurrent_futures.ThreadPoolExecutor(max_workers=1) as executor:
            
            future = executor.submit(next, self.container.decode(self.stream))
            
            try:
                frame = future.result(timeout)
                
                if frame is None:
                    return None
                
                if isinstance(frame, av.VideoFrame):
                    frame = frame.reformat(format='rgb24')
            
            except concurrent_futures.TimeoutError:
                self.logger.warning("Timeout while reading frame ...")
                return None
            
            except StopIteration:
                self.logger.warning("No frame found ...")
                return None
            
            except Exception as e:
                self.logger.error(format_exc())
                self.stop()
                raise e
        
        end_read_dt = datetime.now()
        
        return FramePacket(
            device=self.device,
            frame=frame.to_ndarray(),
            start_read_dt=start_read_dt,
            end_read_dt=end_read_dt
        )

# ------------------- FFMPEG READERS ------------------- #

class CameraDeviceReader(FFMPEGReader):
    def __init__(self, camera: CameraDevice):
        super().__init__(device=camera, logger_name=f"{__class__.__name__}@{camera.name}")
        
    def start(self):
        super().start(
            file_string=f'video={self.device.device_id}',
            options={
                'video_size': f'{self.device.width}x{self.device.height}', 
                'framerate': f'{self.device.fps}/1',
                # 'pixel_format': f'{self.device.pixel_format}',
                # 'vcodec': f'{self.device.vcodec}'
            },
            format='dshow'
        )

class AudioDeviceReader(FFMPEGReader):
    def __init__(self, audio_device: AudioDevice):
        super().__init__(device=audio_device, logger_name=f"{__class__.__name__}@{audio_device.name}")
        
    def start(self):
        super().start(
            file_string=f'audio={self.device.device_id}', 
            options={
                'ar': f'{self.device.sample_rate}',
                'channels': f'{self.device.channels}',
                'sample_size': f'{self.device.sample_size}',
                'audio_buffer_size': f'{self.device.audio_buffer_size}'
            },
            format='dshow',
        )

