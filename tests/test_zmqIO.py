import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from camera_capture_system.zmqIO import ZMQPublisher, ZMQSubscriber


class TestZMQPublisher(unittest.TestCase):

    @patch('camera_capture_system.zmqIO.Context', autospec=True)
    def test_publish(self, mock_context):
        mock_socket = MagicMock()
        mock_context.return_value.socket.return_value = mock_socket

        publisher = ZMQPublisher()
        camera_frame_packet = MagicMock()
        camera_frame_packet.dump.return_value = (np.array([[1, 2], [3, 4]], dtype=np.uint8), MagicMock())

        publisher.publish(camera_frame_packet)

        mock_socket.send_json.assert_called_once()
        mock_socket.send.assert_called_once()


class TestZMQSubscriber(unittest.TestCase):
    
    @patch('camera_capture_system.zmqIO.Context', autospec=True)
    def test_receive(self, mock_context):
        mock_socket = MagicMock()
        mock_context.return_value.socket.return_value = mock_socket

        mock_socket.recv_json.return_value = {
            "image_data": {
                "dtype": "uint8",
                "shape": [2, 2]
            },
            "camera": {
                "uuid": "test",
                "id": 0,
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "name": "test",
                "position": "test"
            },
            "start_read_timestamp": 0.0,
            "end_read_timestamp": 0.0
        }
        mock_socket.recv.return_value = np.array([[1, 2], [3, 4]], dtype=np.uint8)

        subscriber = ZMQSubscriber()
        result = subscriber.recieve()

        mock_socket.recv_json.assert_called_once()
        mock_socket.recv.assert_called_once()

