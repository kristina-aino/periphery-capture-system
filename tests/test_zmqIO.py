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
    return zmqIO.ZMQSender(
        host_name="127.0.0.1",
        port=1025,
    )
@pytest.fixture
def zmq_reciever():
    return zmqIO.ZMQReciever(
        host_name="127.0.0.1",
        port=1025,
    )
@pytest.fixture
def frame_packet():
    return datamodel.FramePacket(
        device=datamodel.PeripheryDevice(
            uuid="uuid",
            description="description",
            publishing_port=1025
        ),
        frame=np.ndarray([1, 2, 3]),
        start_read_dt=datetime.now(),
        end_read_dt=datetime.now()
    )

def test_zmq_close(zmq_sender, zmq_reciever):
    zmq_sender.close()
    zmq_reciever.close()
    
    assert not zmq_sender.is_ok()
    assert not zmq_reciever.is_ok()

def test_zmq_sender_send(zmq_sender, zmq_reciever, frame_packet):
    
    sender_thread = Thread(target=zmq_sender.send, args=(frame_packet,))
    reciever_thread = Thread(target=zmq_reciever.recieve)
    
    reciever_thread.start()
    sleep(0.1)
    sender_thread.start()
    
    sender_thread.join()
    reciever_thread.join()
    