import pytest
import numpy as np

from time import sleep
from pydantic import ValidationError
from datetime import datetime
from threading import Thread

import periphery_capture_system.zmqIO as zmqIO
import periphery_capture_system.datamodel as datamodel

@pytest.fixture
def zmq_sender():
    return zmqIO.ZMQSender(host="127.0.0.1", port=1025)
@pytest.fixture
def zmq_reciever():
    return zmqIO.ZMQReciever(host="127.0.0.1", port=1025)
@pytest.fixture
def frame_packet():
    return datamodel.FramePacket(
        device=datamodel.PeripheryDevice(
            device_id="uuid",
            name="test_device",
        ),
        frame=np.ndarray([1, 2, 3]),
        start_read_dt=datetime.now(),
        end_read_dt=datetime.now()
    )

def test_zmq_sender_open_close(zmq_sender):
    zmq_sender.start()
    assert zmq_sender.is_active()
    zmq_sender.stop()
    assert not zmq_sender.is_active()

def test_zmq_reciever_open_close(zmq_reciever):
    zmq_reciever.start()
    assert zmq_reciever.is_active()
    zmq_reciever.stop()
    assert not zmq_reciever.is_active()

def test_zmq_sender_send(zmq_sender, zmq_reciever, frame_packet):
    
    zmq_sender.start()
    zmq_reciever.start()
    
    sender_thread = Thread(target=zmq_sender.send, args=(frame_packet,))
    reciever_thread = Thread(target=zmq_reciever.recieve)
    
    reciever_thread.start()
    sleep(0.1)
    sender_thread.start()
    
    sender_thread.join()
    reciever_thread.join()
    
    zmq_sender.stop()
    zmq_reciever.stop()