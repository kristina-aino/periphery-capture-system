import unittest
import numpy as np

from unittest.mock import MagicMock, patch, PropertyMock
from asyncio import get_event_loop
from datetime import datetime

from camera_capture_system.zmqIO import ZMQPublisher, ZMQSubscriber
from camera_capture_system.datamodel import CameraFramePacket

class TestZMQPublisher(unittest.TestCase):

    @patch('camera_capture_system.zmqIO.Context')
    def test_is_ok(self, mock_context):
        mock_socket = MagicMock()
        type(mock_socket).closed = PropertyMock(return_value=False)
        mock_context.return_value.socket.return_value = mock_socket
        type(mock_context.return_value).closed = PropertyMock(return_value=False)

        publisher = ZMQPublisher(host_name="127.0.0.1", port=10000)
        self.assertTrue(publisher.is_ok())

    @patch('camera_capture_system.zmqIO.Context')
    def test_close(self, mock_context):
        mock_socket = MagicMock()
        mock_context.return_value.socket.return_value = mock_socket

        publisher = ZMQPublisher(host_name="127.0.0.1", port=10000)
        publisher.close()

        mock_socket.close.assert_called_once()
        mock_context.return_value.term.assert_called_once()

    @patch('camera_capture_system.zmqIO.Context')
    def test_prepare_packet(self, mock_context):
        mock_socket = MagicMock()
        mock_context.return_value.socket.return_value = mock_socket

        publisher = ZMQPublisher(host_name="127.0.0.1", port=10000)
        camera_frame_packet = MagicMock()
        camera_frame_packet.dump.return_value = (np.array([[1, 2], [3, 4]], dtype=np.uint8), MagicMock())

        frame, data = publisher.prepare_packet(camera_frame_packet)

        self.assertTrue(frame.flags["C_CONTIGUOUS"])

    @patch('camera_capture_system.zmqIO.Context')
    def test_publish(self, mock_context):
        mock_socket = MagicMock()
        type(mock_socket).closed = PropertyMock(return_value=False)
        mock_context.return_value.socket.return_value = mock_socket
        type(mock_context.return_value).closed = PropertyMock(return_value=False)

        publisher = ZMQPublisher(host_name="127.0.0.1", port=10000)
        camera_frame_packet = MagicMock()
        camera_frame_packet.dump.return_value = (np.array([[1, 2], [3, 4]], dtype=np.uint8), MagicMock())

        publisher.publish(camera_frame_packet)

        mock_socket.send_json.assert_called_once()
        mock_socket.send.assert_called_once()

    @patch('camera_capture_system.zmqIO.Context')
    def test_async_publish(self, mock_context):
        mock_socket = MagicMock()
        type(mock_socket).closed = PropertyMock(return_value=False)
        mock_context.return_value.socket.return_value = mock_socket
        type(mock_context.return_value).closed = PropertyMock(return_value=False)

        publisher = ZMQPublisher(host_name="127.0.0.1", port=10000)
        camera_frame_packet = MagicMock()
        camera_frame_packet.dump.return_value = (np.array([[1, 2], [3, 4]], dtype=np.uint8), MagicMock())

        loop = get_event_loop()
        loop.run_until_complete(publisher.async_publish(camera_frame_packet))

        mock_socket.send_json.assert_called_once()
        mock_socket.send.assert_called_once()
        

class TestZMQSubscriber(unittest.TestCase):

    @patch('camera_capture_system.zmqIO.Context')
    def test_is_ok(self, mock_context):
        mock_socket = MagicMock()
        type(mock_socket).closed = PropertyMock(return_value=False)
        mock_context.return_value.socket.return_value = mock_socket
        type(mock_context.return_value).closed = PropertyMock(return_value=False)

        subscriber = ZMQSubscriber(host_name="127.0.0.1", port=10000)
        self.assertTrue(subscriber.is_ok())

    @patch('camera_capture_system.zmqIO.Context')
    def test_close(self, mock_context):
        mock_socket = MagicMock()
        type(mock_socket).closed = PropertyMock(return_value=False)
        mock_context.return_value.socket.return_value = mock_socket
        type(mock_context.return_value).closed = PropertyMock(return_value=False)

        subscriber = ZMQSubscriber(host_name="127.0.0.1", port=10000)
        subscriber.close()

        mock_socket.close.assert_called_once()
        mock_context.return_value.term.assert_called_once()

    @patch('camera_capture_system.zmqIO.Context')
    def test_receive(self, mock_context):
        mock_socket = MagicMock()
        type(mock_socket).closed = PropertyMock(return_value=False)
        mock_context.return_value.socket.return_value = mock_socket
        type(mock_context.return_value).closed = PropertyMock(return_value=False)

        mock_socket.poll.return_value = True
        mock_socket.recv_json.return_value = {
            "image_data": {
                "dtype": "uint8",
                "shape": [2, 2]
            },
            "camera": {
                "uuid": "test",
                "id": 0,
                "publishing_port": 5555,
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "name": "test",
                "position": "test",
            },
            "start_read_timestamp": datetime.now().timestamp(),
            "end_read_timestamp": datetime.now().timestamp(),
        }
        mock_socket.recv.return_value = np.array([[1, 2], [3, 4]], dtype=np.uint8).tobytes()

        subscriber = ZMQSubscriber(host_name="127.0.0.1", port=10000)
        result = subscriber.recieve()

        mock_socket.recv_json.assert_called_once()
        mock_socket.recv.assert_called_once()

        self.assertIsInstance(result, CameraFramePacket)

    @patch('camera_capture_system.zmqIO.Context')
    def test_async_receive(self, mock_context):
        mock_socket = MagicMock()
        type(mock_socket).closed = PropertyMock(return_value=False)
        mock_context.return_value.socket.return_value = mock_socket
        type(mock_context.return_value).closed = PropertyMock(return_value=False)

        mock_socket.poll.return_value = True
        mock_socket.recv_json.return_value = {
            "image_data": {
                "dtype": "uint8",
                "shape": [2, 2]
            },
            "camera": {
                "uuid": "test",
                "id": 0,
                "publishing_port": 5555,
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "name": "test",
                "position": "test",
            },
            "start_read_timestamp": datetime.now().timestamp(),
            "end_read_timestamp": datetime.now().timestamp(),
        }
        mock_socket.recv.return_value = np.array([[1, 2], [3, 4]], dtype=np.uint8).tobytes()

        subscriber = ZMQSubscriber(host_name="127.0.0.1", port=10000)

        loop = get_event_loop()
        result = loop.run_until_complete(subscriber.async_recieve())

        mock_socket.recv_json.assert_called_once()
        mock_socket.recv.assert_called_once()

        self.assertIsInstance(result, CameraFramePacket)
