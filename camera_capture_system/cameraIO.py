from time import sleep
from logging import getLogger
from datetime import datetime
from traceback import format_exc
import cv2
from platform import system

from .datamodel import Camera, CameraFramePacket

# ------------------- Logging ------------------- #

logger = getLogger(__name__)

# ------------------- OpenCV Camera Input Reader ------------------- #

CV2_BACKENDS = {
    "Windows": cv2.CAP_ANY,
    "Linux": cv2.CAP_V4L2,
    "Darwin": cv2.CAP_AVFOUNDATION
}

class CameraInputReader:
    def __init__(self, camera: Camera, max_consec_failures: int = 10):
        
        self.max_consec_failures = max_consec_failures
        self.camera = camera
        self.fail_counter = 0
        
        logger.debug(f"{self.camera.uuid} :: Initializing capture with backend {CV2_BACKENDS.get(system(), cv2.CAP_ANY)} ...")
        logger.debug(f"{self.camera.uuid} :: Camera information: {self.camera}")
        
        # set backend and capture
        self.capture = cv2.VideoCapture(self.camera.id, CV2_BACKENDS.get(system(), cv2.CAP_ANY))
        
        # set capture parameters and test
        set_fps = self.capture.set(cv2.CAP_PROP_FPS, self.camera.fps)
        set_width = self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera.width)
        set_height = self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera.height)
        
        if not set_fps:
            logger.warn(f"{self.camera.uuid} :: Failed to set fps to {self.camera.fps}, using {self.capture.get(cv2.CAP_PROP_FPS)} instead.")
        if not set_width:
            logger.warn(f"{self.camera.uuid} :: Failed to set width to {self.camera.width}, using {self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)} instead.")
        if not set_height:
            logger.warn(f"{self.camera.uuid} :: Failed to set height to {self.camera.height}, using {self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)} instead.")
        
        # initialize camera befor use
        logger.info(f"{self.camera.uuid} :: Start Camera Initialization ...")
        self.initialize()
        
    def is_open(self):
        return self.capture.isOpened()
    
    def initialize(self):
        
        logger.info(f"{self.camera.uuid} :: Checking camera functionality ...")
        try:
            # try open camera
            while not self.is_open() and self.fail_counter < self.max_consec_failures:
                
                logger.info(f"{self.camera.uuid} :: Attempting to open capture {self.fail_counter}/{self.max_consec_failures} ...")
                
                self.capture.open(self.camera.id, CV2_BACKENDS.get(system(), cv2.CAP_ANY))
                sleep(0.5)
                self.fail_counter += 1
                assert self.fail_counter < self.max_consec_failures, f"{self.camera.uuid} :: Failed to open capture after {self.fail_counter} attempts"
            self.fail_counter = 0
            
            # try read frame
            ret = self.read()
        except:
            raise
        logger.info(f"{self.camera.uuid} :: Camera check successful!")
        
    
    def close(self):
        self.capture.release()
        logger.info(f"{self.camera.uuid} :: Capture closed!")
        
    def read_(self):
        
        assert self.is_open(), f" {self.camera.uuid} :: AsyncCameraCapture is not open but attempted to read"

        try:
            # try read frame and define metadata
            start_read_dt = datetime.now()
            ok, frame = self.capture.read()
            end_read_dt = datetime.now()
        
            # count incorrect reads
            if not ok:
                raise RuntimeError(f"{self.camera.uuid} :: reader returned not ok")
            
            # successfull read, reset fail counter and return
            self.fail_counter = 0
            return frame, start_read_dt, end_read_dt
        
        except KeyboardInterrupt:
            raise
        except RuntimeError as e:
            
            # log warning and increment fail counter
            logger.warning(f"{self.camera.uuid} :: reader issue for {self.fail_counter}/{self.max_consec_failures} frames ...")
            logger.warning(f"{self.camera.uuid} :: Exception: {e}")
            self.fail_counter += 1
            
            # close and throw if too many failures
            if self.fail_counter >= self.max_consec_failures:
                self.close()
                raise Exception(f"{self.camera.uuid} :: no frame found after {self.fail_counter} attempts")
            
            # otherwise wait and return None
            sleep(0.5)
            return None
        except:
            logger.error(f"{self.camera.uuid} :: Unexpected error: {format_exc()}")
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
        