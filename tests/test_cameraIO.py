import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from camera_capture_system.cameraIO import CameraInputReader
from camera_capture_system.datamodel import Camera

@patch('camera_capture_system.cameraIO.cv2.VideoCapture')
@patch('camera_capture_system.cameraIO.CV2_BACKENDS', new_callable=MagicMock())
@patch('camera_capture_system.cameraIO.CameraInputReader.check')
def test_camera_input_reader(mock_cv2_video_capture, mock_cv_backends, mock_check):
    
    # initialize the mock capture
    mock_capture = MagicMock()
    mock_capture.read.return_value = (True, MagicMock())
    mock_capture.read.side_effect = lambda *args: print(f"read called with {args}") or (True, MagicMock())
    mock_cv2_video_capture.return_value = mock_capture
    
    mock_backend = MagicMock()
    mock_cv_backends.get.return_value = mock_backend
    
    
    # initialize the tested conmponents
    camera = Camera(
        uuid="test",
        id=0,
        width=1920,
        height=1080,
        fps=30,
        name="test",
        position="test",
    )
    cam_ir = CameraInputReader(camera)
    
    # assert that the camera reader is open
    assert cam_ir.is_open()
    
    # assert check was called
    mock_check.assert_called_once()
    
    # assert that video capture was initialized correctly
    mock_cv2_video_capture.assert_called()