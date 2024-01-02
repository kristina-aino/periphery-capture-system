import pytest
from unittest.mock import patch, MagicMock
from camera_capture_system import core

@patch('camera_capture_system.core.CameraInputReader')
@patch('camera_capture_system.core.ZMQPublisher')
def test_multi_camera_capture_and_publish_init(mock_ZMQPublisher, mock_CameraInputReader):
    cameras = [MagicMock() for _ in range(3)]
    ports = [8000, 8001, 8002]
    host_name = "127.0.0.1"
    max_consec_reader_failures = 10
    PUBLISHING_MODE = "ALL_AVAILABLE"

    multi_cam_cap_pub = core.MultiCameraCaptureAndPublish(cameras, ports, host_name, max_consec_reader_failures, PUBLISHING_MODE)

    assert len(multi_cam_cap_pub.async_camera_captures) == len(cameras)
    assert len(multi_cam_cap_pub.async_zmq_publishers) == len(ports)
    assert all(isinstance(capture, MagicMock) for capture in multi_cam_cap_pub.async_camera_captures)
    assert all(isinstance(publisher, MagicMock) for publisher in multi_cam_cap_pub.async_zmq_publishers)
    assert multi_cam_cap_pub.PUBLISHING_MODE == PUBLISHING_MODE

    mock_CameraInputReader.assert_called()
    mock_ZMQPublisher.assert_called()


@patch('camera_capture_system.core.CameraInputReader')
@patch('camera_capture_system.core.ZMQPublisher')
def test_multi_camera_capture_and_publish_init_with_unequal_cameras_and_ports(mock_ZMQPublisher, mock_CameraInputReader):
    cameras = [MagicMock() for _ in range(3)]
    ports = [8000, 8001]
    host_name = "127.0.0.1"
    max_consec_reader_failures = 10
    PUBLISHING_MODE = "ALL_AVAILABLE"

    with pytest.raises(AssertionError):
        core.MultiCameraCaptureAndPublish(cameras, ports, host_name, max_consec_reader_failures, PUBLISHING_MODE)


@patch('camera_capture_system.core.CameraInputReader')
@patch('camera_capture_system.core.ZMQPublisher')
def test_multi_camera_capture_and_publish_stop(mock_ZMQPublisher, mock_CameraInputReader):
    cameras = [MagicMock() for _ in range(3)]
    ports = [8000, 8001, 8002]
    host_name = "127.0.0.1"
    max_consec_reader_failures = 10
    PUBLISHING_MODE = "ALL_AVAILABLE"

    multi_cam_cap_pub = core.MultiCameraCaptureAndPublish(cameras, ports, host_name, max_consec_reader_failures, PUBLISHING_MODE)
    multi_cam_cap_pub.stop()

    for capture in multi_cam_cap_pub.async_camera_captures:
        capture.close.assert_called()

    for publisher in multi_cam_cap_pub.async_zmq_publishers:
        publisher.close.assert_called()
        


@patch('camera_capture_system.core.ZMQSubscriber')
def test_multi_camera_zmq_subscriber_init(mock_ZMQSubscriber):
    cameras = [MagicMock() for _ in range(3)]
    ports = [8000, 8001, 8002]
    host_name = "127.0.0.1"

    multi_cam_zmq_sub = core.MultiCameraZMQSubscriber(cameras, ports, host_name)

    assert len(multi_cam_zmq_sub.zmq_subscribers) == len(ports)
    assert all(isinstance(subscriber, MagicMock) for subscriber in multi_cam_zmq_sub.zmq_subscribers)

    mock_ZMQSubscriber.assert_called()


@patch('camera_capture_system.core.ZMQSubscriber')
def test_multi_camera_zmq_subscriber_is_ok(mock_ZMQSubscriber):
    cameras = [MagicMock() for _ in range(3)]
    ports = [8000, 8001, 8002]
    host_name = "127.0.0.1"

    multi_cam_zmq_sub = core.MultiCameraZMQSubscriber(cameras, ports, host_name)

    for subscriber in multi_cam_zmq_sub.zmq_subscribers:
        subscriber.is_ok.return_value = True

    assert multi_cam_zmq_sub.is_ok()


@patch('camera_capture_system.core.ZMQSubscriber')
def test_multi_camera_zmq_subscriber_stop(mock_ZMQSubscriber):
    cameras = [MagicMock() for _ in range(3)]
    ports = [8000, 8001, 8002]
    host_name = "127.0.0.1"

    multi_cam_zmq_sub = core.MultiCameraZMQSubscriber(cameras, ports, host_name)
    multi_cam_zmq_sub.stop()

    for subscriber in multi_cam_zmq_sub.zmq_subscribers:
        subscriber.close.assert_called()


@patch('camera_capture_system.core.ZMQSubscriber')
def test_multi_camera_zmq_subscriber_receive(mock_ZMQSubscriber):
    cameras = [MagicMock() for _ in range(3)]
    ports = [8000, 8001, 8002]
    host_name = "127.0.0.1"
    
    sub_mock = MagicMock()
    sub_mock.is_ok.return_value = True
    sub_mock.recieve.return_value = "test"
    mock_ZMQSubscriber.return_value = sub_mock

    multi_cam_zmq_sub = core.MultiCameraZMQSubscriber(cameras, ports, host_name)
    
    generator = multi_cam_zmq_sub.receive()
    packages = next(generator)
    
    assert len(packages) == len(ports)
    assert all([package == "test" for package in packages])
    
    generator.close()