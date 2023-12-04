import time
from asyncio import run as async_run
from numpy import uint8

from camera_capture_system.zmqIO import ZMQPublisher

from numpy.random import randint




publisher = ZMQPublisher()


sends = 1000
image = randint(0, 255, (1920, 1080, 3)).astype(uint8)
dt = time.perf_counter()
for i in range(sends):
    publisher.publish(image, {"test": i})
    time.sleep(1/300)
print(f"Send time: {sends/(time.perf_counter() - dt)}")
