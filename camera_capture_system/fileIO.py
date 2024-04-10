import os
import cv2

from time import sleep
from traceback import format_exc
from datetime import datetime
from logging import getLogger
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Queue, Process, Pool
from queue import Empty as QueueEmpty
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

def save_videos_(frames_packets_queue: Queue, video_name: str, video_params: VideoParameters):
    
    video_writers = []
    
    try:
        first_frame_packets = frames_packets_queue.get()
        
        # extract cam uuids
        cam_uuids = [fp.camera.uuid for fp in first_frame_packets]
        video_uris = [os.path.join(video_params.save_path, cam_uuid, f"{video_name}.{video_params.output_format}") for cam_uuid in cam_uuids]
        first_frames = [fp.camera_frame for fp in first_frame_packets]
        
        video_writers = [
            cv2.VideoWriter(
                filename = video_uris[i],
                fourcc=cv2.VideoWriter_fourcc(*video_params.codec),
                fps=video_params.fps, frameSize=(first_frames[i].shape[1], first_frames[i].shape[0])
            ) for i in range(len(first_frame_packets))]
        
        
        logger.info(f"{__name__} - start saving video: {video_name} ...")
        
        # write frames to video
        for i in range(len(first_frame_packets)):
            video_writers[i].write(first_frame_packets[i].camera_frame)
        while frames_packets_queue.qsize() > 0 and frames_packets_queue.empty() is False:
            
            
            frame_packets = frames_packets_queue.get(timeout=1)
            
            for i in range(len(frame_packets)):
                video_writers[i].write(frame_packets[i].camera_frame)
        
        logger.info(f"{__name__} done saving video: {video_name} ...")
    
    except KeyboardInterrupt:
        logger.warn(f"{__name__} - KeyboardInterrupt ...")
        raise
    except QueueEmpty:
        logger.warn(f"{__name__} - queue is empty ...")
    except:
        logger.error(format_exc())
        raise
    finally:
        for vr in video_writers:
            if vr.isOpened():
                vr.release()
    
def save_image_(frame_packet: CameraFramePacket, image_uri: str, image_params: ImageParameters):
    try:
        if image_params.output_format == "jpg":
            cv2.imwrite(image_uri, frame_packet.camera_frame, [int(cv2.IMWRITE_JPEG_QUALITY), image_params.jpg_quality])
        elif image_params.output_format == "png":
            cv2.imwrite(image_uri, frame_packet.camera_frame, [int(cv2.IMWRITE_PNG_COMPRESSION), image_params.png_compression])
    except Exception as e:
        logger.error(f"{__name__} - Error while saving image: {e}")

# ------------------- Functionality ------------------- #

class CaptureVideoSaver(MultiCaptureSubscriber):
    
    def __init__(self, cameras: List[Camera], video_params: VideoParameters, host: str = "127.0.0.1"):
        self.logger_suffix = f"{self.__class__.__name__} -"
        
        self.video_params = video_params
        
        create_camera_save_directories(cameras=cameras, save_path=video_params.save_path)
        
        self.frames_per_video = video_params.fps * video_params.seconds
        self.save_video_processes = None
        
        self.frame_packets_queues = []
        
        super().__init__(cameras=cameras, host=host, q_size=self.frames_per_video)
        
    def start(self):
        
        logger.info(f"{self.logger_suffix} starting ...")
        
        # check if already started
        if self.save_video_processes is not None:
            logger.warning(f"{self.logger_suffix} trying to start a process that has already started")
            return
        
        self.save_video_processes = []
        super().start()
        
        logger.info(f"{self.logger_suffix} started !")
        
    def stop(self, terminate: bool = True):
        
        logger.info(f"{self.logger_suffix} stopping ...")
        
        # check if already stopped
        if self.save_video_processes is None:
            logger.warning(f"{self.logger_suffix} trying to stop a process that has already stopped")
            return
        
        # close queue
        for queue in self.frame_packets_queues:
            while queue.qsize() > 0:
                try:
                    queue.get_nowait()
                except QueueEmpty:
                    break
            queue.close()
        
        for process in self.save_video_processes:
            try:
                process.join(timeout=1)
            except TimeoutError:
                logger.warn(f"{self.logger_suffix} TimeoutError while waiting for process to finish, terminating")
                process.terminate()
            except Exception as e:
                logger.error(f"{self.logger_suffix} Error while waiting for process to finish: {e}")
                process.terminate()
            
            process.close()
        
        self.save_video_processes = None
        
        super().stop(terminate=terminate)
        
        logger.info(f"{self.logger_suffix} stopped !")
    
    def save_video(self) -> bool:
        
        if self.save_video_processes is None:
            logger.warning(f"{self.logger_suffix} trying to save video without starting the saver")
            return False
        
        try:
            
            # clean up processes
            self.save_video_processes = [process for process in self.save_video_processes if process.is_alive()]
            self.frame_packets_queues = [queue for queue in self.frame_packets_queues if queue.qsize() > 0]
            
            
            logger.info(f"{self.logger_suffix} reading frames ...")
            video_name = datetime.now().isoformat().replace(":", "-")
            captured_frames = 0
            current_frames_queue = Queue(maxsize=self.frames_per_video)
            
            while captured_frames < self.frames_per_video:
                
                frame_packets = self.read(block=True, timeout=1, synchronous_read=True)
                
                if frame_packets is None:
                    continue
                
                current_frames_queue.put(frame_packets)
                captured_frames += 1
                
                q_sizes = [cs.output_queue.qsize() for cs in self.capture_subscribers.values()]
                
                logger.info(f"{self.logger_suffix} captured frames: {captured_frames}/{self.frames_per_video} --- capture q sizes: {q_sizes} --- number of active write queues: {len(self.frame_packets_queues)}")
            
            logger.info(f"{self.logger_suffix} done reading frames !")
            
            # after collecting enough frames, prepare processes for saving in the background
            current_save_video_process = Process(
                target=save_videos_, 
                args=(
                    current_frames_queue,
                    video_name, 
                    self.video_params
                ),
                daemon=True)
            
            # append process reference and queue reference
            self.save_video_processes.append(current_save_video_process)
            self.frame_packets_queues.append(current_frames_queue)
            
            # start processes
            current_save_video_process.start()
        
        except KeyboardInterrupt:
            logger.info(f"{self.logger_suffix} KeyboardInterrupt ...")
            self.stop()
            raise
        except:
            logger.error(format_exc())
            self.stop()
            raise
        
        return True

class CaptureImageSaver(MultiCaptureSubscriber):
    
    def __init__(self, cameras: List[Camera], image_params: ImageParameters, host: str = "127.0.0.1", num_workers: int = 8):
        self.logger_suffix = f"{self.__class__.__name__} -"
        
        create_camera_save_directories(cameras=cameras, save_path=image_params.save_path)
        
        # initialize Capture subscribers
        super().__init__(cameras=cameras, host=host, q_size=1)
        
        self.image_params = image_params
        
        # instantiate a multiprocessing worker pool placeholder for saving images
        self.pool = None
        self.num_workers = num_workers
        self.results = []
    
    def start(self):
        
        logger.info(f"{self.logger_suffix} starting ...")
        
        # check if already started
        if self.pool is not None:
            logger.warning(f"{self.logger_suffix} trying to start a process that has already started")
            return
        
        logger.info(f"{self.logger_suffix} starting capture image saver ...")
        self.pool = Pool(self.num_workers)
        super().start()
        
        logger.info(f"{self.logger_suffix} started !")
    
    def stop(self, terminate: bool = True):
        
        logger.info(f"{self.logger_suffix} stopping ...")
        
        # check if already stopped
        if self.pool is None:
            logger.warning(f"{self.logger_suffix} trying to stop a process that has already stopped")
            return
        
        logger.info(f"{self.logger_suffix} stopping capture image saver and await current process results ...")
        
        # wait for all results or terminate
        for result in self.results:
            try:
                logger.info(f"{self.logger_suffix} waiting for process {result} to finish ...")
                result.get(timeout=1)
            except TimeoutError:
                logger.warn(f"{self.logger_suffix} TimeoutError while waiting for process to finish")
            except Exception as e:
                logger.error(f"{self.logger_suffix} Error while waiting for process to finish: {e}")
        
        self.pool.close()
        
        for worker in self.pool._pool:
            try:
                logger.info(f"{self.logger_suffix} joining worker {worker} ...")
                worker.join(timeout=1)
            except TimeoutError:
                logger.warn(f"{self.logger_suffix} TimeoutError while joining worker, terminating ...")
                worker.terminate()
            except Exception as e:
                logger.error(f"{self.logger_suffix} Error while joining worker: {e}, terminating ...")
                worker.terminate()
        
        if terminate:
            self.pool.terminate()
        self.pool = None
        super().stop(terminate=terminate)
        
        logger.info(f"{self.logger_suffix} stopped !")
        
    def save_image(self, visualize: bool = False) -> bool:
        
        
        # create datetime for image name
        image_name = datetime.now().isoformat().replace(":", "-")
        
        # read frames
        frame_packets = self.read(block=True, timeout=1)
        if any([frame_packet is None for frame_packet in frame_packets]):
            logger.warn(f"{self.logger_suffix} some or all captures returned None, skipping ...")
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