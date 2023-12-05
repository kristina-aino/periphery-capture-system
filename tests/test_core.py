import unittest
import asyncio
from unittest.mock import patch, mock_open, MagicMock, AsyncMock

from camera_capture_system.core import load_all_cameras_from_config, AsyncPublisher, AsyncCameraCapture, SyncCameraCaptureAndPublish


class TestLoadAllCamerasFromConfig(unittest.TestCase):
    @patch('builtins.open', new_callable=mock_open)
    @patch('camera_capture_system.core.load')
    @patch('camera_capture_system.core.Camera')
    def test_load_all_cameras_from_config(self, mock_camera, mock_load, mock_file):
        mock_load.return_value = {
            "uuid1": {"id": "1", "name": "camera1"}, 
            "uuid2": {"id": "2", "name": "camera2"}
        }

        cameras = load_all_cameras_from_config("./test_not_a_real_file.json")

        mock_file.assert_called_once_with("./test_not_a_real_file.json", "r")
        mock_load.assert_called_once()
        self.assertEqual(len(cameras), 2)
        mock_camera.assert_any_call(id="1", name="camera1", uuid="uuid1")
        mock_camera.assert_any_call(id="2", name="camera2", uuid="uuid2")


class TestAsyncPublisher(unittest.TestCase):
    @patch('camera_capture_system.core.ZMQPublisher')
    def setUp(self, mock_zmq_publisher):
        self.publisher = AsyncPublisher()

    def test_is_ok(self):
        self.publisher.zmq_publisher.socket.closed = False
        self.publisher.zmq_publisher.context.closed = False
        self.assertTrue(self.publisher.is_ok())

        self.publisher.zmq_publisher.socket.closed = True
        self.publisher.zmq_publisher.context.closed = False
        self.assertFalse(self.publisher.is_ok())

        self.publisher.zmq_publisher.socket.closed = False
        self.publisher.zmq_publisher.context.closed = True
        self.assertFalse(self.publisher.is_ok())

    @patch('camera_capture_system.core.AsyncPublisher.is_ok', return_value=True)
    def test_publish(self, mock_is_ok):
        frame = MagicMock()
        data = MagicMock()

        asyncio.run(self.publisher.publish(frame, data))
        self.publisher.zmq_publisher.publish.assert_called_once_with(frame, data)



class TestAsyncCameraCapture(unittest.TestCase):
    @patch('camera_capture_system.core.CameraInputReader')
    @patch('camera_capture_system.core.Camera')
    def setUp(self, mock_camera, mock_camera_input_reader):
        self.camera_capture = AsyncCameraCapture(mock_camera)
        self.camera_capture.camera_reader = mock_camera_input_reader

    def test_is_ok(self):
        self.camera_capture.camera_reader.is_open.return_value = True
        self.assertTrue(self.camera_capture.is_ok())

        self.camera_capture.camera_reader.is_open.return_value = False
        self.assertFalse(self.camera_capture.is_ok())

    @patch('camera_capture_system.core.AsyncCameraCapture.is_ok', return_value=True)
    def test_capture(self, mock_is_ok):
        frame = MagicMock()
        self.camera_capture.camera_reader.read.return_value = (True, frame)

        result = asyncio.run(self.camera_capture.capture())

        self.assertEqual(result[0], frame)
        self.assertIn('start_read_timestamp', result[1])
        self.assertIn('end_read_timestamp', result[1])
        self.assertIn('camera_data', result[1])