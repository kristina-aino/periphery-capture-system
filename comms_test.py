import traceback
import logging
import time
import numpy as np

from camera_capture_system.zmqIO import ZMQSubscriber
import asyncio


sub = ZMQSubscriber()

dt = time.perf_counter()
for i in range(10000):
    sub.recieve()
    print(i)
print(f"Recieve time: {10000/(time.perf_counter() - dt)}")
