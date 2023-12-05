from time import sleep
from logging import getLogger
import cv2
from platform import system
from pydantic import BaseModel, Field, StrictStr, Strict
from typing_extensions import Annotated

# ------------------- Logging ------------------- #

logger = getLogger(__name__)

# ------------------- Datamodel ------------------- #

StrictNonEmptyStr = Annotated[StrictStr, Field(min_length=1), Strict()]

class Camera(BaseModel):
    uuid: StrictNonEmptyStr # unique identifier for the camera
    id: Annotated[int, Field(ge=0), Strict()] # index of the camera in the system (opencv index)
    width: Annotated[int, Field(ge=640, le=3840), Strict()]
    height: Annotated[int, Field(ge=480, le=2160), Strict()]
    fps: Annotated[int, Field(ge=15, le=120), Strict()]
    name: StrictNonEmptyStr
    position: StrictNonEmptyStr

# ------------------- OpenCV Camera Input Reader ------------------- #

CV2_BACKENDS = {
    "Windows": cv2.CAP_MSMF,
    "Linux": cv2.CAP_V4L2,
    "Darwin": cv2.CAP_AVFOUNDATION
}

class CameraInputReader:
    def __init__(self, camera: Camera):
        
        logger.debug(f"{camera.uuid} :: Initializing capture with backend {CV2_BACKENDS.get(system(), cv2.CAP_ANY)} ...")
        logger.debug(f"{camera.uuid} :: Camera information: {camera}")
        
        self.cam_uuid = camera.uuid
        
        backend = CV2_BACKENDS.get(system(), cv2.CAP_ANY)
        self.capture = cv2.VideoCapture(camera.id, backend)
        
        self.capture.set(cv2.CAP_PROP_FPS, camera.fps)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, camera.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.height)
        
        logger.info(f"{self.cam_uuid} :: Start Camera Initialization ...")
        self.check()
        
    def is_open(self):
        return self.capture.isOpened()
    def read(self):
        return self.capture.read()
    def close(self):
        logger.info(f"{self.cam_uuid} :: Closing capture ...")
        self.capture.release()
            
    def check(self, max_attempts: int = 10) -> None:
        attempts = 0
        
        while attempts < max_attempts:
            
            logger.debug(f"{self.cam_uuid} :: Appempting to opening capture ...")
            if not self.capture.isOpened():
                logger.warn(f"{self.cam_uuid} :: Capture is not open. Retrying...")
                attempts += 1
                sleep(0.33)
                
            logger.debug(f"{self.cam_uuid} :: Appempting to retrieve frame ...")
            ret, _ = self.capture.read()
            if ret:
                logger.info(f"{self.cam_uuid} :: Initialization successfull, valid frame received.")
                return
            
            logger.warn(f"{self.cam_uuid} :: Failed to receive valid image from camera. Retrying...")
            attempts += 1
            sleep(0.33)
            
        self.close()
        raise RuntimeError(f"{self.cam_uuid} :: Failed to receive image from camera after {max_attempts} attempts.")    
