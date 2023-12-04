import unittest
import asyncio
import numpy as np
import unittest

from unittest.mock import AsyncMock
from unittest.mock import patch, call, Mock

from camera_capture_system.camera_functionality import Camera, CameraInputReader


def test_camera():
    # Step 1: Create an instance of the Camera class with test data
    camera = Camera(
        id=0,
        uuid="test",
        width=1920,
        height=1080,
        fps=30,
        port=5555,
    )

    # Step 2: Assert that each attribute of the instance matches the test data
    assert camera.id == 0
    assert camera.uuid == "test"
    assert camera.width == 1920
    assert camera.height == 1080
    assert camera.fps == 30
    assert camera.port == 5555
    