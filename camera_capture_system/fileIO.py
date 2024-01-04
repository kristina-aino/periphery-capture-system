import os
import cv2
import time

from traceback import format_exc
from datetime import datetime
from logging import getLogger
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Queue, Process

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

def write_videos_from_zmq_stream(multi_zmq_sub: MultiCaptureSubscriber, video_params: VideoParameters):
        
    # ensure directory exists
    assert os.path.exists(video_params.save_path), f"save path {video_params.save_path} does not exist"
    
    frames_per_video = video_params.fps * video_params.seconds
    save_video_processes = {}
    video_frame_queues = {cam.uuid: Queue() for cam in multi_zmq_sub.cameras}

    try:
        
        while True:

            logger.info(f"reading frames ...")
            collected_frames = 0
            video_id = datetime.now().isoformat().replace(":", "-")
            
            # collect frames until specified video length
            while collected_frames < frames_per_video:

                # read frames from zmq
                all_frame_packets = multi_zmq_sub.receive()
                if not all_frame_packets or not all(all_frame_packets):
                    continue

                collected_frames += 1
                for frame_packet in all_frame_packets:
                    video_frame_queues[frame_packet.camera.uuid].put(frame_packet)
            
            
            # after collecting enough frames, prepare processes for saving in the background
            for cam in multi_zmq_sub.cameras:
                
                # assign save path to camera subdirectory  and create directory if it does not exist
                save_path = os.path.join(video_params.save_path, cam.uuid)
                if not os.path.exists(save_path):
                    logger.info(f"creating directory for {cam.uuid} ...")
                    os.makedirs(save_path)
                
                # assign process to save video
                save_video_processes[cam.uuid] = Process(
                    target=save_video_from_queue, 
                    args=(
                        multi_zmq_sub.frame_packet_Q[cam.uuid],
                        os.path.join(save_path, f"{video_id}.mp4"),
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
        multi_zmq_sub.stop()
        logger.info("all save video processes stopped")


def save_images_from_zmq_stream(multi_zmq_sub: MultiCaptureSubscriber, image_params: ImageParameters):

    assert os.path.exists(image_params.save_path), f"save path {image_params.save_path} does not exist"

    executor = ThreadPoolExecutor(8)
    try:
        
        while True:
            
            # try read frames
            read_dt = datetime.now().isoformat().replace(":", "-")
            
            all_frame_packets = multi_zmq_sub.receive()
            if not all_frame_packets or not all(all_frame_packets):
                continue

            # save frames
            for frame_packet in all_frame_packets:
                
                # create cam directory and create if nessesary
                save_path = os.path.join(image_params.save_path, frame_packet.camera.camera_uuid)
                if not os.path.exists(save_path):
                    logger.info(f"creating directory for {frame_packet.camera.camera_uuid} ...")
                    os.makedirs(save_path)    
                
                # create image uri and start savve image thread
                image_uri = os.path.join(save_path, read_dt)
                executor.submit(save_image(frame_packet.camera_frame, image_uri, image_params))

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt ...")
    except:
        logger.error(format_exc())
        raise
    finally:
        executor.shutdown(wait=True)
        multi_zmq_sub.stop()