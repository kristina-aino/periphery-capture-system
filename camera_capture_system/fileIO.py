import os
import cv2

from time import sleep
from traceback import format_exc
from datetime import datetime
from logging import getLogger
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Queue, Process, Pool, Event
from queue import Empty as QueueEmpty
from typing import List

from .datamodel import CameraFramePacket, ImageParameters, VideoParameters, Camera
from .core import MultiInputStreamSubscriber

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

class SaveVideoProcess(Process):
    def __init__(self, video_params: VideoParameters, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.logger_prefix = f"{self.__class__.__name__} -"
        
        self.expected_video_length = video_params.fps * video_params.seconds
        
        self.frames_packets_queue = Queue(maxsize=self.expected_video_length)
        self.video_params = video_params
        self.video_writers = []
        
        self.is_started = Event()
        self.is_finished = Event()
        self.is_failed = Event()
        
    def cleanup(self):
        
        logger.info(f"{self.logger_prefix} cleaning up ...")
        
        # close video writers
        for vr in self.video_writers:
            if vr is not None and vr.isOpened():
                vr.release()
        
        # close queue
        if self.frames_packets_queue is None:
            logger.info(f"{self.logger_prefix} queue is None, nothing to cleanup !")
            return
        else:
            logger.info(f"{self.logger_prefix} queue is not empty, emptying queue ...")
            
            while self.frames_packets_queue.qsize() > 0:
                try:
                    self.frames_packets_queue.get(timeout=1)
                except QueueEmpty:
                    break
        self.frames_packets_queue.close()
        
        logger.info(f"{self.logger_prefix} cleanup completed !")
        
    def run(self):
        
        self.is_started.set()
        read_attempts = 0
        
        try:
            
            
            saved_frames = 0
            read_attempts = 0
            
            while saved_frames < self.expected_video_length:
                
                # try getting frame packets
                try:
                    frame_packets = self.frames_packets_queue.get(timeout=1)
                except QueueEmpty:
                    logger.info(f"{self.logger_prefix} - no frames to save, waiting ...")
                    read_attempts += 1
                    if read_attempts > 10:
                        raise TimeoutError("Timeout while waiting for frames to save")
                    sleep(1)
                    continue
                
                # extract camera frames
                camera_frames = [fp.frames for fp in frame_packets]
                
                # on first frame
                if saved_frames == 0:
                    # - set video_uri's on first frame recieved
                    video_name = frame_packets[0].end_read_dt.isoformat().replace(":", "-")
                    video_uris = [
                            os.path.join(self.video_params.save_path, fp.camera.uuid, f"{video_name}.{self.video_params.output_format}")
                        for fp in frame_packets]
                    
                    logger.info(f"{__name__} - start saving video: {video_name} ...")
                    
                    # - initialize video writers
                    self.video_writers = [
                        cv2.VideoWriter(
                            filename = video_uris[i], 
                            fourcc=cv2.VideoWriter_fourcc(*self.video_params.codec),
                            fps=self.video_params.fps, 
                            frameSize=(cf.shape[1], cf.shape[0]))
                        for (i, cf) in enumerate(camera_frames)]
                
                # save frames
                for i in range(len(self.video_writers)):
                    self.video_writers[i].write(camera_frames[i])
                
                saved_frames += 1
            
            logger.info(f"{__name__} done saving video: {video_name} ...")
            
        except KeyboardInterrupt:
            logger.warn(f"{__name__} - KeyboardInterrupt ...")
            self.is_failed.set()
        except TimeoutError:
            logger.error(f"{__name__} - TimeoutError while waiting for frames to save")
            self.is_failed.set()
        except:
            logger.error(f"{__name__} - Error while saving video: {format_exc()}")
            self.is_failed.set()
            raise
        finally:
            self.cleanup()
            self.is_finished.set()
    
def save_image_(frame_packet: CameraFramePacket, image_uri: str, image_params: ImageParameters):
    try:
        if image_params.output_format == "jpg":
            cv2.imwrite(image_uri, frame_packet.frames, [int(cv2.IMWRITE_JPEG_QUALITY), image_params.jpg_quality])
        elif image_params.output_format == "png":
            cv2.imwrite(image_uri, frame_packet.frames, [int(cv2.IMWRITE_PNG_COMPRESSION), image_params.png_compression])
    except Exception as e:
        logger.error(f"{__name__} - Error while saving image: {e}")

# ------------------- Functionality ------------------- #
class CaptureVideoSaver(MultiInputStreamSubscriber):
    
    def __init__(self, cameras: List[Camera], video_params: VideoParameters, host: str = "127.0.0.1"):
        self.logger_suffix = f"{self.__class__.__name__} -"
        
        self.video_params = video_params
        
        create_camera_save_directories(cameras=cameras, save_path=video_params.save_path)
        
        self.frames_per_video = video_params.fps * video_params.seconds
        self.save_video_processes = None
        
        super().__init__(devices=cameras, host=host, q_size=self.frames_per_video)
        
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
        
        # close processes
        for process in self.save_video_processes:
            if process is None:
                continue
            try:
                process.cleanup()
            except TimeoutError:
                logger.warn(f"{self.logger_suffix} TimeoutError while waiting for process to finish, terminting ...")
                process.terminate()
        
        self.save_video_processes = None
        super().stop(terminate=terminate)
        logger.info(f"{self.logger_suffix} stopped !")
    
    def save_video(self) -> bool:
        
        if self.save_video_processes is None:
            logger.warning(f"{self.logger_suffix} trying to save video without starting the saver")
            return False
        
        try:
            
            # clear the queues
            self.empty_queues()
            
            # clean old processes
            self.save_video_processes = [svp for svp in self.save_video_processes if not svp.is_finished.is_set()]
            
            
            logger.info(f"{self.logger_suffix} reading frames ...")
            
            current_save_video_process = SaveVideoProcess(self.video_params, daemon=True)
            self.save_video_processes.append(current_save_video_process)
            
            if not self.save_video_processes[0].is_started.is_set():
                logger.info(f"{self.logger_suffix} starting leading process ...")
                self.save_video_processes[0].start()
            
            collected_frames = 0
            while collected_frames < self.frames_per_video:
                
                # print(f"qsize: {[svp.frames_packets_queue.qsize() for svp in self.save_video_processes]}")
                # print(f"alive: {[svp.is_alive() for svp in self.save_video_processes]}")
                # print(f"started: {[svp.is_started.is_set() for svp in self.save_video_processes]}")
                # print(f"finished: {[svp.is_finished.is_set() for svp in self.save_video_processes]}")
                # print(f"failed: {[svp.is_failed.is_set() for svp in self.save_video_processes]}")
                
                frame_packets = self.read(block=True, timeout=1, synchronous_read=True)
                
                self.logger.debug(f"collected frames: {collected_frames}/{self.frames_per_video} - packet status: {frame_packets is not None}")
                
                if frame_packets is None:
                    continue
                
                if current_save_video_process.is_failed.is_set():
                    logger.warn(f"{self.logger_suffix} current process failed, stopping collection !")
                    break
                current_save_video_process.frames_packets_queue.put(frame_packets, timeout=1)
                
                q_sizes = [cs.output_queue.qsize() for cs in self.capture_subscribers.values()]
                logger.info(f"{self.logger_suffix} \n\tcaptured frames: {collected_frames}/{self.frames_per_video} \n\tcapture q sizes: {q_sizes} \n\tnumber active write processes: {len(self.save_video_processes)}")
                
                collected_frames += 1
            
            logger.info(f"{self.logger_suffix} done reading frames !")
            
        except KeyboardInterrupt:
            logger.info(f"{self.logger_suffix} KeyboardInterrupt ...")
            self.stop()
            raise
        except:
            logger.error(format_exc())
            self.stop()
            raise
        
        return True

class CaptureImageSaver(MultiInputStreamSubscriber):
    
    def __init__(self, cameras: List[Camera], image_params: ImageParameters, host: str = "127.0.0.1", num_workers: int = 8):
        self.logger_suffix = f"{self.__class__.__name__} -"
        
        create_camera_save_directories(cameras=cameras, save_path=image_params.save_path)
        
        # initialize Capture subscribers
        super().__init__(devices=cameras, host=host, q_size=1)
        
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
        if frame_packets is None:
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
                    cv2.imshow(frame_packet.camera.uuid, frame_packet.frames)
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