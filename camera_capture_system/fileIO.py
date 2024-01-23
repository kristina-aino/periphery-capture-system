import os
import cv2

from time import sleep
from traceback import format_exc
from datetime import datetime
from logging import getLogger
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Queue, Process, Pool
from typing import List

from .datamodel import CameraFramePacket, ImageParameters, VideoParameters, Camera
from .core import MultiCaptureSubscriber

# ------------------- Logging ------------------- #

logger = getLogger(__name__)

# ------------------- Helpers ------------------- #

def create_camera_save_directories(cameras: List[Camera], save_path: str):
    
    # check save path exists
    assert os.path.exists(save_path), f"save path {save_path} does not exist"
    
    # create cam directory and create if necessary
    for cam in cameras:
        save_path_ = os.path.join(save_path, cam.uuid)
        if not os.path.exists(save_path_):
            os.makedirs(save_path_)
            logger.info(f"directory {save_path_} created")

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

def save_image_(frame_packet: CameraFramePacket, image_uri: str, image_params: ImageParameters):
    try:
        if image_params.output_format == "jpg":
            cv2.imwrite(image_uri, frame_packet.camera_frame, [int(cv2.IMWRITE_JPEG_QUALITY), image_params.jpg_quality])
        elif image_params.output_format == "png":
            cv2.imwrite(image_uri, frame_packet.camera_frame, [int(cv2.IMWRITE_PNG_COMPRESSION), image_params.png_compression])
    except Exception as e:
        logger.error(f"Error while saving image: {e}")

# ------------------- Functionality ------------------- #

class CaptureVideoSaver(MultiCaptureSubscriber):
    
    def __init__(self, cameras: List[Camera], video_params: VideoParameters, host: str = "127.0.0.1"):
        
        raise NotImplementedError("CaptureVideoSaver is not implemented yet")
        
        create_camera_save_directories(cameras=cameras, save_path=video_params.save_path)
    
        self.frames_per_video = video_params.fps * video_params.seconds
        self.save_video_processes = {}
        self.video_frame_queues = {cam.uuid: Queue() for cam in cameras}
        
        
        
        # TODO: 
    # def stop(self):
    #     pass
    # def start(self):
        
    #     try:
            
    #         while True:

    #             logger.info(f"reading frames ...")
    #             collected_frames = 0
    #             video_name = datetime.now().isoformat().replace(":", "-")
                
    #             # collect frames until specified video length
    #             while collected_frames < frames_per_video:

    #                 # read frames from zmq
    #                 all_frame_packets = multi_capture_subscriber.read()
    #                 if not all(all_frame_packets):
    #                     logger.warn("some or all frames where not read, skipping ...")
    #                     continue
                    
    #                 collected_frames += 1
    #                 for frame_packet in all_frame_packets:
    #                     video_frame_queues[frame_packet.camera.uuid].put(frame_packet)
                
                
    #             # after collecting enough frames, prepare processes for saving in the background
    #             for cam in multi_capture_subscriber.cameras:
                    
    #                 # assign process to save video
    #                 video_uri = os.path.join(video_params.save_path, cam.uuid, f"{video_name}.mp4")
    #                 save_video_processes[cam.uuid] = Process(
    #                     target=save_video_from_queue, 
    #                     args=(
    #                         multi_capture_subscriber.frame_packet_Q[cam.uuid],
    #                         video_uri,
    #                         video_params),
    #                     daemon=True)
                
    #             # start processes
    #             for uuid in save_video_processes:
    #                 save_video_processes[uuid].start()

    #     except KeyboardInterrupt:
    #         logger.info("KeyboardInterrupt ...")
    #     except:
    #         logger.error(format_exc())
    #         raise
    #     finally:
    #         for cam_uuid in save_video_processes:
    #             if save_video_processes[cam_uuid].is_alive():
    #                 save_video_processes[cam_uuid].join()
    #                 save_video_processes[cam_uuid].close()
    #         for cam_uuid in video_frame_queues:
    #             video_frame_queues[cam_uuid].close()
    #         multi_capture_subscriber.stop()
    #         logger.info("all save video processes stopped")


class CaptureImageSaver(MultiCaptureSubscriber):
    
    def __init__(self, cameras: List[Camera], image_params: ImageParameters, host: str = "127.0.0.1", q_size: int = 1, num_workers: int = 8):
        
        create_camera_save_directories(cameras=cameras, save_path=image_params.save_path)
        
        # initialize Capture subscribers
        super().__init__(cameras=cameras, host=host, q_size=q_size)
        
        self.image_params = image_params
        
        # instantiate a multiprocessing worker pool placeholder for saving images
        self.pool = None
        self.num_workers = num_workers
        self.results = []
    
    def start(self):
        # check if already started
        if self.pool is not None:
            logger.warning("trying to start a process that has already started")
            return
        
        logger.info("starting capture image saver ...")
        self.pool = Pool(self.num_workers)
        super().start()
    
    def stop(self, terminate: bool = True):
        # check if already stopped
        if self.pool is None:
            logger.warning("trying to stop a process that has already stopped")
            return
        
        logger.info("stopping capture image saver and await current process results ...")
        
        # wait for all results or terminate
        for result in self.results:
            try:
                logger.info(f"waiting for process {result} to finish ...")
                result.get(timeout=1)
            except TimeoutError:
                logger.warn("TimeoutError while waiting for process to finish")
            except Exception as e:
                logger.error(f"Error while waiting for process to finish: {e}")
        
        self.pool.close()
        
        for worker in self.pool._pool:
            try:
                logger.info(f"joining worker {worker} ...")
                worker.join(timeout=1)
            except TimeoutError:
                logger.warn("TimeoutError while joining worker, terminating ...")
                worker.terminate()
            except Exception as e:
                logger.error(f"Error while joining worker: {e}, terminating ...")
                worker.terminate()
        
        if terminate:
            self.pool.terminate()
        self.pool = None
        super().stop(terminate=terminate)
        
    def save_image(self, visualize: bool = False) -> bool:
        
        # create datetime for image name
        image_name = datetime.now().isoformat().replace(":", "-")
        
        # read frames
        frame_packets = self.read()
        if any([frame_packet is None for frame_packet in frame_packets]):
            logger.warn("some or all captures returned None, skipping ...")
            return False
        
        # clean up results
        self.results = [result for result in self.results if not result.ready()]
        logger.info(f"not-ready process results in queue: {len(self.results)}")
        
        try:
            
            # save frames
            for frame_packet in frame_packets:
                
                # start save image process
                image_uri = os.path.join(self.image_params.save_path, frame_packet.camera.uuid, f"{image_name}.{self.image_params.output_format}")
                
                logger.info(f"saving images in {image_uri} ...")
                
                result = self.pool.apply_async(save_image_, (frame_packet, image_uri, self.image_params))
                self.results.append(result)
                
                # visualize
                if visualize:
                    cv2.imshow(frame_packet.camera.uuid, frame_packet.camera_frame)
                    cv2.waitKey(1)
            
            # # Check for errors
            # for result in self.results:
            #     try:
            #         result.get(timeout=1)  # This will raise an exception if the function failed
            #     except Exception as e:
            #         logger.error(f"Error in save_image function: {e}")
            
        except:
            self.stop()
            cv2.destroyAllWindows()
            raise
        
        return True