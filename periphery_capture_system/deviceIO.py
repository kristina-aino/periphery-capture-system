import av

from capture_devices import devices
from json import dump as json_dump
from json import load as json_load
from pywinusb import hid
from typing import Union, Tuple, List
from abc import ABC, abstractmethod
from logging import getLogger
from time import sleep
from logging import getLogger
from datetime import datetime
from traceback import format_exc
from platform import system
from numpy import frombuffer

from .datamodel import FramePacket, PeripheryDevice, CameraDevice, AudioDevice

# ------------------- DEVICE UTILS ------------------- #


def get_all_devices_ffmpeg():
    """
        - load all devices
        - remove prefix
        - zip every other element and remove the last \n from alternative name
        - filter dublicate device_pnp names
    """
    all_devices_ffmpeg_raw = devices.run_with_param(alt_name=True, result_=True)
    all_devices_ffmpeg_raw = [field.split(" : ")[1] for field in all_devices_ffmpeg_raw]
    
    video_devices_ffmpeg = [(a[:-1], b) for a, b in zip(all_devices_ffmpeg_raw[1::2], all_devices_ffmpeg_raw[::2]) if "_pnp_" in a]
    video_devices_ffmpeg = list(dict(video_devices_ffmpeg).items())
    
    audio_devices_ffmpeg = [(a[:-1], b) for a, b in zip(all_devices_ffmpeg_raw[1::2], all_devices_ffmpeg_raw[::2]) if "_cm_" in a]
    audio_devices_ffmpeg = list(dict(audio_devices_ffmpeg).items())
    
    return {
        "videoDevices": video_devices_ffmpeg,
        "audioDevices": audio_devices_ffmpeg
    }



def save_periphery_devices_to_config(devices: List[PeripheryDevice], config_file: str = "./raw_devices.json"):
    json_dump(devices, config_file)

def load_all_periphery_devices_from_config(config_file: str = "./raw_devices.json") -> List[CameraDevice]:
    return [CameraDevice(**cam) for cam in json_load(config_file)]


# def load_all_audio_devices_from_config(config_path: str) -> List[AudioDevice]:
#     with open(config_path, "r") as f:
#         audio_devices = load(f)
#     return [AudioDevice(uuid=dev_uuid, **audio_devices[dev_uuid]) for dev_uuid in audio_devices]



# ------------------- BASE CLASS ------------------- #


def start_video_ffmpeg_container(device_id: str, width: int = 1920, height: int = 1080, fps: int = 60):
    return av.open(
        file=f'video={device_id}', 
        format='dshow',
        options={
            'video_size': f'{width}x{height}', 
            'framerate': f'{fps}'
        })




# class DeviceReader(ABC):
#     def __init__(self, logger_name: str):
#         self.logger = getLogger(logger_name)
        
#     @abstractmethod
#     def start(self):
#         self.logger.debug(f"Starting ...")
        
#     @abstractmethod
#     def stop(self):
#         self.logger.debug(f"Stopping ...")
        
#     @abstractmethod
#     def is_ok(self):
#         pass
    
#     @abstractmethod
#     def read_(self) -> Union[FramePacket, None]:
#         '''
#             Read a frame from the device
#         '''
#         pass
    
#     def read(self) -> Tuple[Union[FramePacket, None], datetime, datetime]:
#         '''
#             call read_
#             test if the frame is not None (indicating a faulty read)
#             and return the raw data
#         '''
        
#         assert self.is_ok(), "reader is not ok ..."
        
#         start_read_dt = datetime.now()
#         out = self.read_()
#         end_read_dt = datetime.now()
        
#         if out is None:
#             self.logger.warn("No valid frame read ...")
        
#         return out, start_read_dt, end_read_dt

# ------------------- FFMPEG READER ------------------- #




# class CameraDeviceReader(DeviceReader):
#     def __init__(
#         self, 
#         camera: CameraDevice, 
#         max_consec_failures: int = 10, 
#         frame_transform: str = None):
        
#         super().__init__(logger_name=f"{__class__.__name__}@{camera.uuid}")
        
#         self.max_consec_failures = max_consec_failures
#         self.camera = camera
#         self.fail_counter = 0
        
#         # set backend and capture
#         self.capture = cv2.VideoCapture(self.camera.id, cv2Backends[system()])
        
#         # set capture parameters and test
#         set_fps = self.capture.set(cv2.CAP_PROP_FPS, self.camera.fps)
#         set_width = self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera.width)
#         set_height = self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera.height)
        
#         if not set_fps or not set_width or not set_height:
#             self.logger.error(f"inccorect set : set_fps = {set_fps}, set_width = {set_width}, set_height = {set_height} ...")
#             raise Exception("Failed to set camera parameters ...")
        
#         # define frame transform
#         if frame_transform == "ROTATE_90_CLOCKWISE":
#             self.frame_transform = lambda frame: rotate(frame, ROTATE_90_CLOCKWISE)
#         elif frame_transform == "ROTATE_90_COUNTERCLOCKWISE":
#             self.frame_transform = lambda frame: rotate(frame, ROTATE_90_COUNTERCLOCKWISE)
#         elif frame_transform == "ROTATE_180":
#             self.frame_transform = lambda frame: rotate(frame, ROTATE_180)
#         else:
#             self.frame_transform = lambda frame: frame
        
        
#         # initialize camera befor use
#         self.initialize()
        
#     def is_open(self):
#         return self.capture.isOpened()
    
#     def initialize(self):
#         super().initialize()
        
#         try:
#             open_attempts = 0
            
#             while True:
                
#                 assert open_attempts < self.max_consec_failures, f"{self.camera.uuid} :: Failed to open capture after {open_attempts} attempts"
                
#                 self.logger.info(f"{self.camera.uuid} :: Attempting to open capture {open_attempts}/{self.max_consec_failures} ...")
                
#                 # try read frames
#                 if not self.is_open():
                    
#                     self.logger.warning(f"{self.camera.uuid} :: Capture not open ...")
                    
#                     self.capture.open(self.camera.id, CV2_BACKENDS.get(system(), cv2.CAP_ANY))
#                     sleep(0.33)
#                     open_attempts += 1
#                     continue
                
#                 read_attempts = 0
#                 for _ in range(self.max_consec_failures):
#                     self.logger.info(f"{self.camera.uuid} :: Capture open, try reading {read_attempts}/{self.max_consec_failures} ...")
                    
#                     ok, _ = self.capture.read()
#                     if ok:
#                         self.logger.info(f"{self.camera.uuid} :: Camera initialization successful!")
#                         return
#                     read_attempts += 1
                
            
#         except:
#             raise
        
#     def stop(self):
#         super().stop()
#         self.capture.release()
#         self.logger.info(f"{self.camera.uuid} :: Capture stoped")
        
#     def read_(self):
        
#         try:
#             # try read frame and define camera read time
#             ok, frame = self.capture.read()
            
#             # count incorrect reads
#             if not ok:
#                 # log warning and increment fail counter
#                 self.logger.warning(f"{self.camera.uuid} :: reader issue for {self.fail_counter}/{self.max_consec_failures} frames ...")
#                 self.fail_counter += 1
#                 # close and throw if too many failures
#                 assert self.fail_counter < self.max_consec_failures, f"{self.camera.uuid} :: no valid frame found after {self.fail_counter} consecutive attempts"
                
#                 sleep(0.33)
#                 return None
            
#             # successfull read, reset fail counter and return
#             self.fail_counter = 0
#             frame = self.frame_transform(frame)
#             return frame
        
#         except KeyboardInterrupt:
#             self.logger.info(f"KeyboardInterrupt ...")
#             self.stop()
#             raise
#         except:
#             self.logger.error(format_exc())
#             self.stop()
#             raise
        
#     def read(self):
#         frames, start_read_dt, end_read_dt = super().read()
#         return CameraFramePacket(device=self.camera, frames=frames, start_read_dt=start_read_dt, end_read_dt=end_read_dt)


# # ------------------- AudioIO ------------------- #

# class AudioInputDevice(DeviceReader):
#     def __init__(self, audio_device: AudioDevice, max_consec_failures: int = 10):
#         super().__init__()
        
#         self.audio_device = audio_device
#         self.max_consec_failures = max_consec_failures
        
#         # create pyaudio instance
#         self.audio = PyAudio()
#         self.stream = self.audio.open(
#                     start=False,
#                     format=paInt16, 
#                     output=audio_device.type == "output",
#                     input=audio_device.type == "input",
#                     input_device_index=audio_device.id,
#                     channels=audio_device.channels,
#                     rate=audio_device.sample_rate,
#                     frames_per_buffer=audio_device.frames_per_buffer)
        
#         self.initialize()
        
#     @classmethod
#     def list_devices(cls):
#         audio = PyAudio()
#         for i in range(audio.get_device_count()):
#             print(audio.get_device_info_by_index(i))
#         audio.terminate()
        
#     def initialize(self):
#         super().initialize()
        
        
#         '''
#             multiple attepmts to start a stream
            
#         '''
#         try:
            
#             start_attempts = 0
            
#             while start_attempts < self.max_consec_failures:
                
#                 self.logger.info(f"Attempting to start audio stream {start_attempts}/{self.max_consec_failures} ...")
                
#                 self.stream.start_stream()
                
#                 if not self.stream.is_active():
#                     self.logger.info(f"Failed to start audio stream ({start_attempts}/{self.max_consec_failures}) ...")
                    
#                     if start_attempts >= self.max_consec_failures:
#                         self.logger.error(f"Failed to start audio stream after {start_attempts} attempts ...")
#                         raise Exception("Failed to start audio stream ...")
                    
#                     start_attempts += 1
#                     sleep(0.33)
#                     continue
                
#                 self.logger.info(f"Audio stream initialized successfully ...")
#                 # self.stream.stop_stream()
#                 break
#         except:
#             raise
        
#     def is_open(self):
#         return not self.stream.is_stopped()
    
#     # def start(self):
#     #     super().start()
#     #     try:
#     #         self.stream.start_stream()
#     #         self.logger.info(f"Audio stream started ...")
#     #     except Exception as e:
#     #         raise e
        
#     def stop(self):
#         super().stop()
#         try:
#             self.stream.stop_stream()
#             self.logger.info(f"Audio stream stopped ...")
#         except Exception as e:
#             raise e
        
#     def read_(self):
#         try:
#             # read audio frames
#             frames = frombuffer(self.stream.read(self.audio_device.frames_per_buffer), dtype="int16")
            
#             # count incorrect reads
#             if frames is None or len(frames) == 0:
#                 # log warning and increment fail counter
#                 self.logger.warning(f"{self.camera.uuid} :: reader issue for {self.fail_counter}/{self.max_consec_failures} frames ...")
#                 self.fail_counter += 1
#                 # close and throw if too many failures
#                 assert self.fail_counter < self.max_consec_failures, f"{self.camera.uuid} :: no valid frame found after {self.fail_counter} consecutive attempts"
                
#                 sleep(0.33)
#                 return None
            
#             # successfull read, reset fail counter and return
#             self.fail_counter = 0
#             return frames
        
#         except KeyboardInterrupt:
#             self.logger.info(f"KeyboardInterrupt ...")
#             self.stop()
#             raise
#         except:
#             self.logger.error(format_exc())
#             self.stop()
#             raise
        
#     def read(self):
#         frames, start_read_dt, end_read_dt = super().read()
#         return AudioFramePacket(device=self.audio_device, frames=frames, start_read_dt=start_read_dt, end_read_dt=end_read_dt)
        