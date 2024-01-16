import os
import cv2

from time import sleep
from traceback import format_exc
from datetime import datetime
from logging import getLogger
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Queue, Process, Pool

from .datamodel import CameraFramePacket, ImageParameters, VideoParameters
from .core import MultiCaptureSubscriber

# ------------------- Logging ------------------- #

logger = getLogger(__name__)

# ------------------- Helpers ------------------- #

def save_video_from_queue(frame_packet_queue: Queue, video_uri: str, video_params: VideoParameters):

    try:
        first_frame = frame_packet_queue.get().camera_frame
        
        video_writer = cv2.VideoWriter(
            filename=video_uri, 
            fourcc=cv2.VideoWriter_fourcc(*video_params.codec),
            fps=video_params.fps,
            frameSize=(first_frame.shape[1], first_frame.shape[0]))

        logger.info(f"start saving video {video_uri} ...")
        
        # write frames to video
        video_writer.write(first_frame)
        for _ in range(video_params.fps * video_params.seconds):
            frame_packet = frame_packet_queue.get()
            video_writer.write(frame_packet.camera_frame)
        
        # release video writer
        video_writer.release()

        logger.info(f"done saving video {video_uri} ...")

    except:
        logger.error(format_exc())
        raise
    finally:
        video_writer.release()

def save_image(frame_packet: CameraFramePacket, image_uri: str, image_params: ImageParameters):

    if image_params.output_format == "jpg":
        cv2.imwrite(image_uri, frame_packet.camera_frame, [int(cv2.IMWRITE_JPEG_QUALITY), image_params.jpg_quality])
    elif image_params.output_format == "png":
        cv2.imwrite(image_uri, frame_packet.camera_frame, [int(cv2.IMWRITE_PNG_COMPRESSION), image_params.png_compression])
    
    return None

# ------------------- Functionality ------------------- #

def save_captures_as_videos(multi_capture_subscriber: MultiCaptureSubscriber, video_params: VideoParameters):
    
    # ensure directory exists
    assert os.path.exists(video_params.save_path), f"save path {video_params.save_path} does not exist"
    
    # create cam directory and create if necessary
    for cam_uuid in multi_capture_subscriber.capture_subsctibers:
        save_path_ = os.path.join(video_params.save_path, cam_uuid)
        if not os.path.exists(save_path_):
            logger.info(f"creating directory for {cam_uuid} ...")
            os.makedirs(save_path_)
    
    
    frames_per_video = video_params.fps * video_params.seconds
    save_video_processes = {}
    video_frame_queues = {cam.uuid: Queue() for cam in multi_capture_subscriber.cameras}
    
    # start multi_capture_subscriber processes
    multi_capture_subscriber.start()
    
    try:
        
        while True:

            logger.info(f"reading frames ...")
            collected_frames = 0
            video_name = datetime.now().isoformat().replace(":", "-")
            
            # collect frames until specified video length
            while collected_frames < frames_per_video:

                # read frames from zmq
                all_frame_packets = multi_capture_subscriber.read()
                if not all(all_frame_packets):
                    logger.warn("some or all frames where not read, skipping ...")
                    continue
                
                collected_frames += 1
                for frame_packet in all_frame_packets:
                    video_frame_queues[frame_packet.camera.uuid].put(frame_packet)
            
            
            # after collecting enough frames, prepare processes for saving in the background
            for cam in multi_capture_subscriber.cameras:
                
                # assign process to save video
                video_uri = os.path.join(video_params.save_path, cam.uuid, f"{video_name}.mp4")
                save_video_processes[cam.uuid] = Process(
                    target=save_video_from_queue, 
                    args=(
                        multi_capture_subscriber.frame_packet_Q[cam.uuid],
                        video_uri,
                        video_params),
                    daemon=True)
            
            # start processes
            for uuid in save_video_processes:
                save_video_processes[uuid].start()

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt ...")
    except:
        logger.error(format_exc())
        raise
    finally:
        for cam_uuid in save_video_processes:
            if save_video_processes[cam_uuid].is_alive():
                save_video_processes[cam_uuid].join()
                save_video_processes[cam_uuid].close()
        for cam_uuid in video_frame_queues:
            video_frame_queues[cam_uuid].close()
        multi_capture_subscriber.stop()
        logger.info("all save video processes stopped")


def save_captures_as_images(multi_capture_subscriber: MultiCaptureSubscriber, image_params: ImageParameters, num_workers: int = 8):
    
    # check save path exists
    assert os.path.exists(image_params.save_path), f"save path {image_params.save_path} does not exist"
    
    # create cam directory and create if necessary
    for cam_uuid in multi_capture_subscriber.capture_subsctibers:
        save_path_ = os.path.join(image_params.save_path, cam_uuid)
        if not os.path.exists(save_path_):
            logger.info(f"creating directory for {cam_uuid} ...")
            os.makedirs(save_path_)
    
    # Create a multiprocessing worker pool 
    pool = Pool(num_workers)
    
    # start multi_capture_subscriber processes
    multi_capture_subscriber.start()
    
    try:
        while True:
            
            # create datetime for image name
            image_name = datetime.now().isoformat().replace(":", "-")
            
            # read frames
            frame_packets = multi_capture_subscriber.read()
            if not all(frame_packets):
                logger.warn("some or all frames where not read, skipping ...")
                sleep(1)
                continue

            # save frames
            for frame_packet in frame_packets:
                # start save image process
                image_uri = os.path.join(image_params.save_path, frame_packet.camera.camera_uuid, image_name)
                pool.apply_async(save_image, (frame_packet.camera_frame, image_uri, image_params))
        
        
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt ...")
    except:
        logger.error(format_exc())
        raise
    finally:
        pool.close()
        pool.join()
        multi_capture_subscriber.stop()