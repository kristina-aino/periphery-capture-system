import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from camera_capture_system.zmqIO import ZMQPublisher, ZMQSubscriber

class TestZMQPublisher(unittest.TestCase):

    @patch('zmqIO.Context', autospec=True)
    def test_publish(self, mock_context):
        mock_socket = MagicMock()
        mock_context.return_value.socket.return_value = mock_socket

        publisher = ZMQPublisher()
        image = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        data = {"test": "data"}

        publisher.publish(image, data)

        mock_socket.send_json.assert_called_once()
        mock_socket.send.assert_called_once()

class TestZMQSubscriber(unittest.TestCase):
    
    @patch('zmqIO.Context', autospec=True)
    def test_receive(self, mock_context):
        mock_socket = MagicMock()
        mock_context.return_value.socket.return_value = mock_socket

        subscriber = ZMQSubscriber()
        result = subscriber.receive()

        mock_socket.recv_json.assert_called_once()
        mock_socket.recv.assert_called_once()
        
        

class TestZMQConnectivity(unittest.TestCase):
    def test_connectivity(self):
        publisher = ZMQPublisher(host_name="172.0.0.1", port=10000)
        subscriber = ZMQSubscriber(host_name="172.0.0.1", port=10000)

        image = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        data = {"test": "data"}

        publisher.publish(image, data)
        result = subscriber.receive()

        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()