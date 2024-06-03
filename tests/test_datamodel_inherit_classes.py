import pytest
from pydantic import ValidationError
from datetime import datetime
import numpy as np

import periphery_capture_system.datamodel as datamodel


@pytest.fixture
def abstract_device():
    return datamodel.PeripheryDevice(
        uuid="uuid",
        description="description",
        publishing_port=1025
    )
@pytest.fixture
def frame():
    return np.ndarray([1, 2, 3])

def test_frame_packet_initialization(abstract_device, frame):
    datamodel.FramePacket(
        device=abstract_device,
        frame=frame,
        start_read_dt=datetime.now(),
        end_read_dt=datetime.now()
    )

def test_frame_packet_dump(abstract_device, frame):
    frame_packet = datamodel.FramePacket(
        device=abstract_device,
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