import pytest
from pydantic import ValidationError

import periphery_capture_system.datamodel as datamodel


"""
    Test the PeripheryDevice classes
"""
def test_periphery_devices_initialization():
    datamodel.PeripheryDevice(
        uuid="uuid",
        description="description",
        publishing_port=1025
    )

@pytest.mark.parametrize(
    "uuid, description, publishing_port", 
    [
        ("", "description", 1025),
        ("uuid", "", 1025),
        ("uuid", "description", 1024),
        ("uuid", "description", 65536)
    ])
def test_periphery_devices_initialization_invalid(uuid, description, publishing_port):
    with pytest.raises(ValidationError):
        datamodel.PeripheryDevice(
            uuid=uuid,
            description=description,
            publishing_port=publishing_port
        )