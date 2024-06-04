import logging

import pytest
from pydantic import ValidationError
from datetime import datetime
import numpy as np

from periphery_capture_system.deviceIO import get_all_devices_ffmpeg


def test_get_all_devices_ffmpeg():
    devices = get_all_devices_ffmpeg()
    
    logging.info(devices)
    
    assert "videoDevices" in devices
    assert "audioDevices" in devices
    assert isinstance(devices["videoDevices"], list)
    assert isinstance(devices["audioDevices"], list)