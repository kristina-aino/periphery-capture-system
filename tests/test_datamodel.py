import pytest
from pydantic import ValidationError
from camera_capture_system.datamodel import Camera, ImageParameters, VideoParameters


def test_camera():
    # Step 1: Create an instance of the Camera class with test data
    camera = Camera(
        uuid="test",
        id=0,
        publishing_port=5555,
        width=1920,
        height=1080,
        fps=30,
        name="test",
        position="test",
    )

    # Step 2: Assert that each attribute of the instance matches the test data
    assert camera.uuid == "test"
    assert camera.id == 0
    assert camera.publishing_port == 5555
    assert camera.width == 1920
    assert camera.height == 1080
    assert camera.fps == 30
    assert camera.name == "test"
    assert camera.position == "test"

@pytest.mark.parametrize(
    "uuid, id, publishing_port, width, height, fps, name, position",
    [
        ("test", -1, 5555, 1920, 1080, 30, "test", "test"),  # Invalid test data (negative id)
        ("test", 0, 1024, 1920, 1080, 30, "test", "test"),  # Invalid test data (publishing port out of range)
        ("test", 0, 65536, 1920, 1080, 30, "test", "test"),  # Invalid test data (publishing port out of range)
        ("test", 0, 5555, 639, 1080, 30, "test", "test"),  # Invalid test data (width out of range)
        ("test", 0, 5555, 1920, 479, 30, "test", "test"),  # Invalid test data (height out of range)
        ("test", 0, 5555, 1920, 1080, 10, "test", "test"),  # Invalid test data (fps out of range)
        ("", 0, 5555, 1920, 1080, 30, "test", "test"),  # Invalid test data (empty uuid)
        ("test", 0, 5555, 1920, 1080, 30, "", "test"),  # Invalid test data (empty name)
        ("test", 0, 5555, 1920, 1080, 30, "test", ""),  # Invalid test data (empty position)
    ]
)
def test_camera_type_validators(uuid, id, publishing_port, width, height, fps, name, position):
    # catch the ValidationError
    with pytest.raises(ValidationError):
        camera = Camera(
            uuid=uuid,
            id=id,
            publishing_port=publishing_port,
            width=width,
            height=height,
            fps=fps,
            name=name,
            position=position,
        )

def test_image_parameters():
    # Test with valid parameters
    params = ImageParameters(save_path="/valid/path", jpg_quality=50, png_compression=50, output_format="jpg")
    assert params.save_path == "/valid/path"
    assert params.jpg_quality == 50
    assert params.png_compression == 50
    assert params.output_format == "jpg"
    
def test_video_parameters():
    # Test with valid parameters
    params = VideoParameters(save_path="/valid/path", fps=30, seconds=10, codec="mp4v")
    assert params.save_path == "/valid/path"
    assert params.fps == 30
    assert params.seconds == 10
    assert params.codec == "mp4v"
    