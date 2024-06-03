import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from periphery_capture_system.deviceIO import CameraInputReader
from periphery_capture_system.datamodel import Camera
from periphery_capture_system.datamodel import CameraFramePacket


@patch('camera_capture_system.cameraIO.cv2.VideoCapture')
def test_camera_input_reader_init(mock_cv2_video_capture):
    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = True
    mock_capture.read.return_value = (True, np.zeros((1920, 1080, 3), dtype=np.uint8))
    mock_cv2_video_capture.return_value = mock_capture
    

    camera = Camera(
        uuid="test",
        id=0,
        publishing_port=5555,
        width=1920,
        height=1080,
        fps=30,
        name="test",
        position="test",
    )
    cam_ir = CameraInputReader(camera)
    
    assert cam_ir.camera == camera
    assert cam_ir.max_consec_failures == 10
    assert cam_ir.fail_counter == 0
    # assert cam_ir.capture == mock_capture


@patch('camera_capture_system.cameraIO.cv2.VideoCapture')
def test_camera_input_reader_not_open(mock_cv2_video_capture):
    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = False
    mock_cv2_video_capture.return_value = mock_capture

    camera = Camera(
        uuid="test",
        id=0,
        publishing_port=5555,
        width=1920,
        height=1080,
        fps=30,
        name="test",
        position="test",
    )
    
    with pytest.raises(AssertionError):
        cam_ir = CameraInputReader(camera, max_consec_failures=1)


@patch('camera_capture_system.cameraIO.cv2.VideoCapture')
def test_camera_input_reader_no_valid_frame(mock_cv2_video_capture):
    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = False
    mock_capture.read.return_value = (False, None)
    mock_cv2_video_capture.return_value = mock_capture

    camera = Camera(
        uuid="test",
        id=0,
        publishing_port=5555,
        width=1920,
        height=1080,
        fps=30,
        name="test",
        position="test",
    )
    
    with pytest.raises(AssertionError):
        cam_ir = CameraInputReader(camera, max_consec_failures=1)


@patch('camera_capture_system.cameraIO.cv2.VideoCapture')
def test_camera_input_reader_is_open(mock_cv2_video_capture):
    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = True
    mock_capture.read.return_value = (True, np.zeros((1920, 1080, 3), dtype=np.uint8))
    mock_cv2_video_capture.return_value = mock_capture

    camera = Camera(
        uuid="test",
        id=0,
        publishing_port=5555,
        width=1920,
        height=1080,
        fps=30,
        name="test",
        position="test",
    )
    cam_ir = CameraInputReader(camera)
    assert cam_ir.is_open()

@patch('camera_capture_system.cameraIO.cv2.VideoCapture')
def test_camera_input_reader_close(mock_cv2_video_capture):
    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = True
    mock_capture.read.return_value = (True, np.zeros((1920, 1080, 3), dtype=np.uint8))
    mock_cv2_video_capture.return_value = mock_capture
    

    camera = Camera(
        uuid="test",
        id=0,
        publishing_port=5555,
        width=1920,
        height=1080,
        fps=30,
        name="test",
        position="test",
    )
    cam_ir = CameraInputReader(camera)
    cam_ir.close()

    mock_capture.release.assert_called_once()

@patch('camera_capture_system.cameraIO.cv2.VideoCapture')
def test_camera_input_reader_read(mock_cv2_video_capture):
    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = True
    mock_capture.read.return_value = (True, np.zeros((1920, 1080, 3), dtype=np.uint8))
    mock_cv2_video_capture.return_value = mock_capture
    

    camera = Camera(
        uuid="test",
        id=0,
        publishing_port=5555,
        width=1920,
        height=1080,
        fps=30,
        name="test"
    )
    cam_ir = CameraInputReader(camera)
    packet = cam_ir.read()

    assert packet is not None
    assert isinstance(packet, CameraFramePacket)

@patch('camera_capture_system.cameraIO.cv2.VideoCapture')
@pytest.mark.asyncio
async def test_camera_input_reader_async_read(mock_cv2_video_capture):
    mock_capture = MagicMock()
    mock_capture.isOpened.return_value = True
    mock_capture.read.return_value = (True, np.zeros((1920, 1080, 3), dtype=np.uint8))
    mock_cv2_video_capture.return_value = mock_capture

    camera = Camera(
        uuid="test",
        id=0,
        publishing_port=5555,
        width=1920,
        height=1080,
        fps=30,
        name="test"
    )
    cam_ir = CameraInputReader(camera)
    packet = await cam_ir.async_read()

    assert packet is not None
    assert isinstance(packet, CameraFramePacket)