import unittest
import asyncio
import numpy as np
import unittest

from unittest.mock import AsyncMock
from unittest.mock import patch, call, Mock
from hydra import compose, initialize

from multicamerasystem.streaming import app, Camera, CameraInputReader, ImageZMQVideoStreamSender, process_camera_frames
from multicamerasystem.datamodel import Camera
from multicamerasystem.IO.readers import CameraInputReader
from multicamerasystem.IO.imageZMQ import ImageZMQVideoStreamSender


class TestApp(unittest.TestCase):

    @patch('multicamerasystem.streaming.process_camera_frames')
    @patch('multicamerasystem.streaming.CameraInputReader')
    @patch('multicamerasystem.streaming.ImageZMQVideoStreamSender')
    def test_app(self, mock_image_sender, mock_input_reader, mock_process_camera_frames):

        # change the input mack moules to return a mock object
        mock_process_camera_frames.new = AsyncMock()
        mock_input_reader.new = Mock()
        mock_image_sender.new = Mock()
        
        # load test config
        with initialize(version_base=None, config_path="test_configs"):
            config = compose(config_name="streaming.yaml")

        # Call the app function
        app(config)

        # Assert that the necessary objects were created and methods were called
        self.assertEqual(mock_image_sender.call_count, 3)
        self.assertEqual(mock_input_reader.call_count, 3)
        self.assertEqual(mock_process_camera_frames.call_count, 3)

        # Assert that the input readers and image senders were closed
        self.assertEqual(mock_input_reader.return_value.close.call_count, 3)
        self.assertEqual(mock_image_sender.return_value.close.call_count, 3)



class TestProcessCameraFreame(unittest.TestCase):
    def setUp(self):
        self.camera = Camera(id=0, uuid="test", port=8000, width=1920, height=1080, fps=30)
        self.input_reader = AsyncMock(spec=CameraInputReader)
        self.image_sender = AsyncMock(spec=ImageZMQVideoStreamSender)
        self.max_fail_counter = 5

    def test_process_camera_frames_success(self):
        asyncio.run(self._test_process_camera_frames_success())
        
    def test_process_camera_frames_failure(self):
        asyncio.run(self._test_process_camera_frames_failure())
        
        
    async def _test_process_camera_frames_success(self):
        self.stop_event = asyncio.Event()
        
        # Simulate a successful read
        self.input_reader.read.return_value = (True, np.array([1, 2, 3], dtype=np.uint8))
        self.input_reader.is_open.return_value = True

        # Set the stop event after a delay
        asyncio.create_task(self.stop_after_delay(self.stop_event))

        # Call the function with the stop event
        await process_camera_frames(self.camera, self.input_reader, self.image_sender, self.max_fail_counter, self.stop_event)

        # Check that the read and send methods were called
        self.input_reader.read.assert_called()
        self.image_sender.send.assert_called()
        
        # Check the type of the frame in the packet
        _, args, _ = self.image_sender.send.mock_calls[0]
        packet = args[0]
        self.assertIsInstance(packet.frame, np.ndarray)
        self.assertEqual(packet.frame.dtype, np.uint8)

    async def _test_process_camera_frames_failure(self):
        self.stop_event = asyncio.Event()
        
        # Simulate a failed read
        self.input_reader.read.return_value = (False, "frame")
        self.input_reader.is_open.return_value = True

        # Set the stop event after a delay
        asyncio.create_task(self.stop_after_delay(self.stop_event))

        # Call the function with the stop event
        with self.assertRaises(AssertionError):
            await process_camera_frames(self.camera, self.input_reader, self.image_sender, self.max_fail_counter, self.stop_event)

        # Check that the read method was called and the send method was not
        self.input_reader.read.assert_called()
        self.image_sender.send.assert_not_called()
        

    async def stop_after_delay(self, stop_event, delay=1):
        await asyncio.sleep(delay)
        stop_event.set()

if __name__ == "__main__":
    unittest.main()