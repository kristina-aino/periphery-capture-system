from time import sleep
from logging import getLogger
from datetime import datetime
from traceback import format_exc
import cv2
from platform import system
from typing import Callable

from .datamodel import Camera, CameraFramePacket

# ------------------- Logging ------------------- #

logger = getLogger(__name__)

# ------------------- OpenCV Camera Input Reader ------------------- #

CV2_BACKENDS = {
    "Windows": cv2.CAP_MSMF,
    "Linux": cv2.CAP_V4L2,
    "Darwin": cv2.CAP_AVFOUNDATION
}

class CameraInputReader:
    def __init__(self, camera: Camera, max_consec_failures: int = 10):
        
        self.max_consec_failures = max_consec_failures
        self.camera = camera
        self.fail_counter = 0
        
        logger.debug(f"{self.camera.uuid} :: Initializing capture with backend {CV2_BACKENDS.get(system(), cv2.CAP_ANY)} ...")
        logger.debug(f"{self.camera.uuid} :: Camera config information: {self.camera}")
        
        # set backend and capture
        self.capture = cv2.VideoCapture(self.camera.id, CV2_BACKENDS.get(system(), cv2.CAP_ANY))
        
        # set capture parameters and test
        set_fps = self.capture.set(cv2.CAP_PROP_FPS, self.camera.fps)
        set_width = self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera.width)
        set_height = self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera.height)
        
        logger.info(f"{self.camera.uuid} :: fps was set to {self.capture.get(cv2.CAP_PROP_FPS)}, success: {set_fps}")
        logger.info(f"{self.camera.uuid} :: width was set to {self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)}, success: {set_width}")
        logger.info(f"{self.camera.uuid} :: height was set to {self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)}, success: {set_height}")
        
        # initialize camera befor use
        self.initialize()
        
    def is_open(self):
        return self.capture.isOpened()
    
    def initialize(self):
        
        logger.info(f"{self.camera.uuid} :: Start Camera Initialization ...")
        
        try:
            open_attempts = 0
            
            while True:
                
                assert open_attempts < self.max_consec_failures, f"{self.camera.uuid} :: Failed to open capture after {open_attempts} attempts"
                
                logger.info(f"{self.camera.uuid} :: Attempting to open capture {open_attempts}/{self.max_consec_failures} ...")
                
                # try read frames
                if not self.is_open():
                    
                    logger.warning(f"{self.camera.uuid} :: Capture not open ...")
                    
                    self.capture.open(self.camera.id, CV2_BACKENDS.get(system(), cv2.CAP_ANY))
                    sleep(0.33)
                    open_attempts += 1
                    continue
                
                read_attempts = 0
                for _ in range(self.max_consec_failures):
                    logger.info(f"{self.camera.uuid} :: Capture open, try reading {read_attempts}/{self.max_consec_failures} ...")
                    
                    ok, _ = self.capture.read()
                    if ok:
                        logger.info(f"{self.camera.uuid} :: Camera initialization successful!")
                        return
                    read_attempts += 1
                
            
        except:
            raise
        
    def close(self):
        self.capture.release()
        logger.info(f"{self.camera.uuid} :: Capture closed")
        
    def read_(self):
        
        assert self.is_open(), f"{self.camera.uuid} :: camera not open but attempted to read"
        
        try:
            # try read frame and define camera read time
            start_read_dt = datetime.now()
            ok, frame = self.capture.read()
            end_read_dt = datetime.now()
            
            # count incorrect reads
            if not ok:
                # log warning and increment fail counter
                logger.warning(f"{self.camera.uuid} :: reader issue for {self.fail_counter}/{self.max_consec_failures} frames ...")
                self.fail_counter += 1
                # close and throw if too many failures
                assert self.fail_counter < self.max_consec_failures, f"{self.camera.uuid} :: no valid frame found after {self.fail_counter} consecutive attempts"
                
                sleep(0.33)
                return None
            
            # successfull read, reset fail counter and return
            self.fail_counter = 0
            return frame, start_read_dt, end_read_dt
        
        except KeyboardInterrupt:
            logger.info(f"KeyboardInterrupt ...")
            self.close()
            raise
        except:
            logger.error(format_exc())
            self.close()
            raise
        
    def read(self):
        ret = self.read_()
        if not ret:
            return None
        return CameraFramePacket(
            camera=self.camera,
            camera_frame=ret[0],
            start_read_dt=ret[1],
            end_read_dt=ret[2])
    
    async def async_read(self):
        ret = self.read_()
        if not ret:
            return None
        return CameraFramePacket(
            camera=self.camera,
            camera_frame=ret[0],
            start_read_dt=ret[1],
            end_read_dt=ret[2])
        