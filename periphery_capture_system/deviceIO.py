from cv2 import VideoCapture, CAP_ANY, CAP_PROP_FPS, CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT, CAP_MSMF, CAP_V4L2, CAP_AVFOUNDATION
from cv2 import rotate, ROTATE_90_CLOCKWISE, ROTATE_90_COUNTERCLOCKWISE, ROTATE_180
from pyaudio import PyAudio, paInt16
from typing import Union
from abc import ABC, abstractmethod
from logging import getLogger
from time import sleep
from logging import getLogger
from datetime import datetime
from traceback import format_exc
from platform import system
from numpy import frombuffer

from .datamodel import AudioDevice, AudioFramePacket
from .datamodel import Camera, CameraFramePacket

# ------------------- OpenCV Backend ------------------- #

CV2_BACKENDS = {
    "Windows": CAP_MSMF,
    "Linux": CAP_V4L2,
    "Darwin": CAP_AVFOUNDATION
}

class InputDevice(ABC):
    def __init__(self):
        self.logger = getLogger(__name__)
        
    # @abstractmethod
    # def start(self):
    #     self.logger.debug(f"Starting ...")
        
    @abstractmethod
    def stop(self):
        self.logger.debug(f"Stopping ...")
        
    @abstractmethod
    def is_open(self):
        pass
    
    @abstractmethod
    def initialize(self):
        '''
            Initialize the reader
            and test the readability of the device
        '''
        self.logger.debug(f"Initializing ...")
        
    @abstractmethod
    def read_(self) -> Union[CameraFramePacket, AudioFramePacket, None]:
        '''
            Read a frame from the device
        '''
        pass
    
    @abstractmethod
    def read(self) -> Union[AudioFramePacket, CameraFramePacket]:
        '''
            test the readability
            call read_
            test if the frame is not None (indicating a faulty read)
            and return the raw data
        '''
        
        assert self.is_open(), "Trying to read from a closed reader ..."
        
        start_read_dt = datetime.now()
        out = self.read_()
        end_read_dt = datetime.now()
        
        if out is None:
            self.logger.warn("No valid frame read ...")
        
        return out, start_read_dt, end_read_dt

# ------------------- OpenCV Camera Input Reader ------------------- #

class CameraInputDevice(InputDevice):
    def __init__(self, camera: Camera, max_consec_failures: int = 10, frame_transform: str = None):
        
        super().__init__()
        
        self.max_consec_failures = max_consec_failures
        self.camera = camera
        self.fail_counter = 0
        
        self.logger.debug(f"{self.camera.uuid} :: Initializing capture with backend {CV2_BACKENDS.get(system(), CAP_ANY)} ...")
        self.logger.debug(f"{self.camera.uuid} :: Camera config information: {self.camera}")
        
        # set backend and capture
        self.capture = VideoCapture(self.camera.id, CV2_BACKENDS.get(system(), CAP_ANY))
        
        # set capture parameters and test
        set_fps = self.capture.set(CAP_PROP_FPS, self.camera.fps)
        set_width = self.capture.set(CAP_PROP_FRAME_WIDTH, self.camera.width)
        set_height = self.capture.set(CAP_PROP_FRAME_HEIGHT, self.camera.height)
        
        self.logger.info(f"{self.camera.uuid} :: fps was set to {self.capture.get(CAP_PROP_FPS)}, success: {set_fps}")
        self.logger.info(f"{self.camera.uuid} :: width was set to {self.capture.get(CAP_PROP_FRAME_WIDTH)}, success: {set_width}")
        self.logger.info(f"{self.camera.uuid} :: height was set to {self.capture.get(CAP_PROP_FRAME_HEIGHT)}, success: {set_height}")
        
        # define frame transform
        if frame_transform == "ROTATE_90_CLOCKWISE":
            self.frame_transform = lambda frame: rotate(frame, ROTATE_90_CLOCKWISE)
        elif frame_transform == "ROTATE_90_COUNTERCLOCKWISE":
            self.frame_transform = lambda frame: rotate(frame, ROTATE_90_COUNTERCLOCKWISE)
        elif frame_transform == "ROTATE_180":
            self.frame_transform = lambda frame: rotate(frame, ROTATE_180)
        else:
            self.frame_transform = lambda frame: frame
        
        
        # initialize camera befor use
        self.initialize()
        
    def is_open(self):
        return self.capture.isOpened()
    
    def initialize(self):
        super().initialize()
        
        try:
            open_attempts = 0
            
            while True:
                
                assert open_attempts < self.max_consec_failures, f"{self.camera.uuid} :: Failed to open capture after {open_attempts} attempts"
                
                self.logger.info(f"{self.camera.uuid} :: Attempting to open capture {open_attempts}/{self.max_consec_failures} ...")
                
                # try read frames
                if not self.is_open():
                    
                    self.logger.warning(f"{self.camera.uuid} :: Capture not open ...")
                    
                    self.capture.open(self.camera.id, CV2_BACKENDS.get(system(), cv2.CAP_ANY))
                    sleep(0.33)
                    open_attempts += 1
                    continue
                
                read_attempts = 0
                for _ in range(self.max_consec_failures):
                    self.logger.info(f"{self.camera.uuid} :: Capture open, try reading {read_attempts}/{self.max_consec_failures} ...")
                    
                    ok, _ = self.capture.read()
                    if ok:
                        self.logger.info(f"{self.camera.uuid} :: Camera initialization successful!")
                        return
                    read_attempts += 1
                
            
        except:
            raise
        
    def stop(self):
        super().stop()
        self.capture.release()
        self.logger.info(f"{self.camera.uuid} :: Capture stoped")
        
    def read_(self):
        
        try:
            # try read frame and define camera read time
            ok, frame = self.capture.read()
            
            # count incorrect reads
            if not ok:
                # log warning and increment fail counter
                self.logger.warning(f"{self.camera.uuid} :: reader issue for {self.fail_counter}/{self.max_consec_failures} frames ...")
                self.fail_counter += 1
                # close and throw if too many failures
                assert self.fail_counter < self.max_consec_failures, f"{self.camera.uuid} :: no valid frame found after {self.fail_counter} consecutive attempts"
                
                sleep(0.33)
                return None
            
            # successfull read, reset fail counter and return
            self.fail_counter = 0
            frame = self.frame_transform(frame)
            return frame
        
        except KeyboardInterrupt:
            self.logger.info(f"KeyboardInterrupt ...")
            self.stop()
            raise
        except:
            self.logger.error(format_exc())
            self.stop()
            raise
        
    def read(self):
        frames, start_read_dt, end_read_dt = super().read()
        return CameraFramePacket(device=self.camera, frames=frames, start_read_dt=start_read_dt, end_read_dt=end_read_dt)


# ------------------- AudioIO ------------------- #

class AudioInputDevice(InputDevice):
    def __init__(self, audio_device: AudioDevice, max_consec_failures: int = 10):
        super().__init__()
        
        self.audio_device = audio_device
        self.max_consec_failures = max_consec_failures
        
        # create pyaudio instance
        self.audio = PyAudio()
        self.stream = self.audio.open(
                    start=False,
                    format=paInt16, 
                    output=audio_device.type == "output",
                    input=audio_device.type == "input",
                    input_device_index=audio_device.id,
                    channels=audio_device.channels,
                    rate=audio_device.sample_rate,
                    frames_per_buffer=audio_device.frames_per_buffer)
        
        self.initialize()
        
    @classmethod
    def list_devices(cls):
        audio = PyAudio()
        for i in range(audio.get_device_count()):
            print(audio.get_device_info_by_index(i))
        audio.terminate()
        
    def initialize(self):
        super().initialize()
        
        
        '''
            multiple attepmts to start a stream
            
        '''
        try:
            
            start_attempts = 0
            
            while start_attempts < self.max_consec_failures:
                
                self.logger.info(f"Attempting to start audio stream {start_attempts}/{self.max_consec_failures} ...")
                
                self.stream.start_stream()
                
                if not self.stream.is_active():
                    self.logger.info(f"Failed to start audio stream ({start_attempts}/{self.max_consec_failures}) ...")
                    
                    if start_attempts >= self.max_consec_failures:
                        self.logger.error(f"Failed to start audio stream after {start_attempts} attempts ...")
                        raise Exception("Failed to start audio stream ...")
                    
                    start_attempts += 1
                    sleep(0.33)
                    continue
                
                self.logger.info(f"Audio stream initialized successfully ...")
                # self.stream.stop_stream()
                break
        except:
            raise
        
    def is_open(self):
        return not self.stream.is_stopped()
    
    # def start(self):
    #     super().start()
    #     try:
    #         self.stream.start_stream()
    #         self.logger.info(f"Audio stream started ...")
    #     except Exception as e:
    #         raise e
        
    def stop(self):
        super().stop()
        try:
            self.stream.stop_stream()
            self.logger.info(f"Audio stream stopped ...")
        except Exception as e:
            raise e
        
    def read_(self):
        try:
            # read audio frames
            frames = frombuffer(self.stream.read(self.audio_device.frames_per_buffer), dtype="int16")
            
            # count incorrect reads
            if frames is None or len(frames) == 0:
                # log warning and increment fail counter
                self.logger.warning(f"{self.camera.uuid} :: reader issue for {self.fail_counter}/{self.max_consec_failures} frames ...")
                self.fail_counter += 1
                # close and throw if too many failures
                assert self.fail_counter < self.max_consec_failures, f"{self.camera.uuid} :: no valid frame found after {self.fail_counter} consecutive attempts"
                
                sleep(0.33)
                return None
            
            # successfull read, reset fail counter and return
            self.fail_counter = 0
            return frames
        
        except KeyboardInterrupt:
            self.logger.info(f"KeyboardInterrupt ...")
            self.stop()
            raise
        except:
            self.logger.error(format_exc())
            self.stop()
            raise
        
    def read(self):
        frames, start_read_dt, end_read_dt = super().read()
        return AudioFramePacket(device=self.audio_device, frames=frames, start_read_dt=start_read_dt, end_read_dt=end_read_dt)
        