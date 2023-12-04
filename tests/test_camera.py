import pytest
from pydantic import ValidationError

from camera_capture_system.camera import Camera


def test_camera():
    # Step 1: Create an instance of the Camera class with test data
    camera = Camera(
        uuid="test",
        id=0,
        width=1920,
        height=1080,
        fps=30,
        name="test",
        position="test",
    )

    # Step 2: Assert that each attribute of the instance matches the test data
    assert camera.uuid == "test"
    assert camera.id == 0
    assert camera.width == 1920
    assert camera.height == 1080
    assert camera.fps == 30
    assert camera.name == "test"
    assert camera.position == "test"

@pytest.mark.parametrize(
    "uuid, id, width, height, fps, name, position",
    [
        ("test", 0, 1920, 1080, 30, "test", "test"),  # Valid test data
        ("test", -1, 1920, 1080, 30, "test", "test"),  # Invalid test data (negative id)
        ("test", 0, 5000, 1080, 30, "test", "test"),  # Invalid test data (width out of range)
        ("test", 0, 1920, 2000, 30, "test", "test"),  # Invalid test data (height out of range)
        ("test", 0, 1920, 1080, 10, "test", "test"),  # Invalid test data (fps out of range)
        ("", 0, 1920, 1080, 30, "test", "test"),  # Invalid test data (empty uuid)
        ("test", 0, 1920, 1080, 30, "", "test"),  # Invalid test data (empty name)
        ("test", 0, 1920, 1080, 30, "test", ""),  # Invalid test data (empty position)
    ]
)
def test_camera_type_validators(uuid, id, width, height, fps, name, position):
    # Use a try-except block to catch the ValidationError
    with pytest.raises(ValidationError):
        camera = Camera(
            uuid=uuid,
            id=id,
            width=width,
            height=height,
            fps=fps,
            name=name,
            position=position,
        )