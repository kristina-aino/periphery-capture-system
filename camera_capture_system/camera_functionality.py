import logging
import cv2
import platform
import time

from pydantic import BaseModel, Field, Strict, PositiveInt, StrictStr, NonEmpty
from typing_extensions import Annotated

# ------------------- Logging ------------------- #

logger = logging.getLogger(__name__)

# ------------------- Datamodel ------------------- #

class Camera(BaseModel):
    id: Annotated[int, Strict(), Field(ge=0)] # index of the camera in the system (opencv index)
    uuid: Annotated[StrictStr, NonEmpty]
    width: Annotated[PositiveInt, Field(ge=640, le=3840), Strict()]
    height: Annotated[PositiveInt, Field(ge=480, le=2160), Strict()]
    fps: Annotated[PositiveInt, Field(ge=15, le=120), Strict()]
    port: Annotated[PositiveInt, Field(ge=1024, le=65534), Strict()]

# ------------------- OpenCV Camera Input Reader ------------------- #

CV2_BACKENDS = {
    "Windows": cv2.CAP_MSMF,
    "Linux": cv2.CAP_V4L2,
    "Darwin": cv2.CAP_AVFOUNDATION
}

class CameraInputReader:
    def __init__(self, camera: Camera):
        
        logger.info(f"{camera.uuid} :: Initializing capture with backend {CV2_BACKENDS.get(platform.system(), cv2.CAP_ANY)} ...")
        logger.info(f"{camera.uuid} :: Camera information: {camera}")
        
        self.cam_uuid = camera.uuid
        
        backend = CV2_BACKENDS.get(platform.system(), cv2.CAP_ANY)
        self.capture = cv2.VideoCapture(camera.id, backend)
        
        self.capture.set(cv2.CAP_PROP_FPS, camera.fps)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, camera.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.height)
        
        self.check()
        
        # cv2.CAP_PROP_BRIGHTNESS # Brightness of the image (only for cameras).
        # cv2.CAP_PROP_CONTRAST # Contrast of the image (only for cameras).
        # cv2.CAP_PROP_SATURATION # Saturation of the image (only for cameras).
        # cv2.CAP_PROP_HUE # Hue of the image (only for cameras).
        # cv2.CAP_PROP_GAIN # Gain of the image (only for cameras).
        # cv2.CAP_PROP_EXPOSURE # Exposure (only for cameras).
        # cv2.CAP_PROP_CONVERT_RGB # Boolean flags indicating whether images should be converted to RGB.
        # cv2.CAP_PROP_RECTIFICATION # Rectification flag for stereo cameras (note: only supported by DC1394 v 2.x backend currently).
        # cv2.CAP_PROP_ISO_SPEED # ISO speed of the camera (only for cameras).
        # cv2.CAP_PROP_BUFFERSIZE # Amount of frames stored in internal buffer memory (note: only supported by some camera drivers).
        
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
            
            logger.info(f"{self.cam_uuid} :: Appempting to opening capture ...")
            if not self.capture.isOpened():
                logger.warn(f"{self.cam_uuid} :: Capture is not open. Retrying...")
                attempts += 1
                time.sleep(0.33)
                
            logger.info(f"{self.cam_uuid} :: Appempting to retrieve frame ...")
            ret, _ = self.capture.read()
            if ret:
                logger.info(f"{self.cam_uuid} :: Valid frame received.")
                return
            
            logger.warn(f"{self.cam_uuid} :: Failed to receive valid image from camera. Retrying...")
            attempts += 1
            time.sleep(0.33)
            
        self.close()
        raise RuntimeError(f"{self.cam_uuid} :: Failed to receive image from camera after {max_attempts} attempts.")    

