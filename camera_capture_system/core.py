
from imagezmq import ImageSender

from .datamodel import Camera



def start_camera_stream(cameras: List[Camera]):

    cameras = load_cameras_from_dict(cfg.cameras)

    logger.info(f"initializing readers and senders...")
    image_senders = [ImageSender() for cam in cameras]
    input_readers = [CameraInputReader(cam) for cam in cameras]

    logger.info(f"starting streams...")
    try:
        tasks = [process_camera_frames(cam, ir, ims, cfg.max_fail_counter) for cam, ir, ims in zip(cameras, input_readers, image_senders)]
        asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks))
    except:
        logger.error(traceback.format_exc())
    finally:
        for ir, ims in zip(input_readers, image_senders):
            ir.close()
            ims.close()


async def process_camera_frames(
    camera: Camera,
    input_reader: CameraInputReader, 
    image_sender: ImageZMQVideoStreamSender,
    max_fail_counter: int,
    stop_event: asyncio.Event = None # for testing
    ) -> None:
    """
        This function is used to read frames 
        from the camera and send them to the image sender asynchronosly
    """
    
    fail_counter = 0
    while input_reader.is_open():

        # Capture frame
        recording_dt = datetime.now()
        ok, frame = await asyncio.to_thread(input_reader.read)
        if not ok:
            logger.warning(f"{camera.uuid} :: reader not ok for {fail_counter}/{max_fail_counter} frames ...")
            fail_counter += 1
            assert fail_counter <= max_fail_counter, f"{camera.uuid} :: no frame found for too long of a period"
            continue
        fail_counter = 0

        # Send frame
        packet = CameraFramePacket(
            camera_uuid=camera.uuid,
            frame=frame,
            timestamp=recording_dt
        )
        await asyncio.to_thread(image_sender.send, packet)

        # cecrd timedelta and log if not zero
        ts_timedelta = datetime.now().timestamp() - recording_dt.timestamp()
        if ts_timedelta > 0:
            logger.debug(f"{camera.uuid} :: current_fps={1 / ts_timedelta}")
        
        # stop event for testing
        if stop_event and stop_event.is_set():
            break