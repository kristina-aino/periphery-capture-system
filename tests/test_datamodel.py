import pytest
from pydantic import ValidationError
from datetime import datetime
import numpy as np

import periphery_capture_system.datamodel as datamodel


@pytest.fixture
def periphery_device():
    return datamodel.PeripheryDevice(
        hardware_id="uuid",
        name="test_device",
    )
@pytest.fixture
def frame():
    return np.ndarray([1, 2, 3])
@pytest.fixture
def camera_device():
    return datamodel.CameraDevice(
        hardware_id="uuid",
        name="test_device",
        # camera_id=0,
        width=640,
        height=480,
        fps=30
    )
@pytest.fixture
def audio_device():
    return datamodel.AudioDevice(
        hardware_id="uuid",
        name="test_device",
        # audio_id=0,
        # audio_type=datamodel.AudioIOType.INPUT,
        sample_rate=44100,
        frames_per_buffer=1024,
        channels=1
    )


def test_frame_packet_initialization(periphery_device, frame):
    datamodel.FramePacket(
        device=periphery_device,
        frame=frame,
        start_read_dt=datetime.now(),
        end_read_dt=datetime.now()
    )

def test_frame_packet_dump(periphery_device, frame):
    frame_packet = datamodel.FramePacket(
        device=periphery_device,
        frame=frame,
        start_read_dt=datetime.now(),
        end_read_dt=datetime.now()
    )
    
    # chek if all keys are present
    fram_packet_dump = frame_packet.dump()
    assert "frame" in fram_packet_dump
    assert "data" in fram_packet_dump

    assert "start_read_timestamp" in fram_packet_dump["data"]
    assert "end_read_timestamp" in fram_packet_dump["data"]
    assert "device" in fram_packet_dump["data"]
    assert "device" in fram_packet_dump["data"]

    assert "type" in fram_packet_dump["data"]["device"]
    assert "parameters" in fram_packet_dump["data"]["device"]
    
    assert "shape" in fram_packet_dump["data"]["frame"]
    assert "dtype" in fram_packet_dump["data"]["frame"]
    
    # check if data is correct
    assert (fram_packet_dump["frame"] == frame).all()


def test_device_initialization(periphery_device, camera_device, audio_device):
    camera_device
    audio_device

def test_video_parameters_initialization():
    datamodel.VideoParameters(
        save_path="path",
        video_output_format=datamodel.VideoFormatType.MP4,
        fps=30,
        seconds=10,
        codec=datamodel.VideoCodecType.MP4V
    )

def image_parameters_initialization():
    datamodel.ImageParameters(
        save_path="path",
        image_output_format=datamodel.ImageFormatType.JPG,
        jpg_quality=100,
        png_compression=0
    )