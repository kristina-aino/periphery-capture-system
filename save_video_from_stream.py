import argparse
import logging
import argparse

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("-op", "--output_path", type=str, required=True, help="output path")

AP.add_argument("--fps", type=int, default=30, help="fps of the output video (usually the same as the cameras)")
AP.add_argument("--seconds", type=int, default=10, help="number of seconds in the output video")

AP.add_argument("-cc", "--cameras_config", type=str, default="./cameras_configs.json", help="path to input configuration file")
AP.add_argument("-hn", "--host_name", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("-p", "--port", type=int, default=10000, help="port to opsn zmq socket on")
AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
AP.add_argument("-ql", "--queue_length", type=str, help="queue length for the camera specific qureues")
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

logging.basicConfig(level=ARGS.logging_level.upper())

# ---------------------------------------------------------------------

# Setp 1: read camera configurations for all cameras
from camera_capture_system.core import load_all_cameras_from_config, MultiCameraZMQSubscriberBufferProcess
from camera_capture_system.fileIO import write_videos_from_video_stream
from camera_capture_system.datamodel import VideoParameters, ImageParameters


cameras = load_all_cameras_from_config(ARGS.cameras_config)
mcsb = MultiCameraZMQSubscriberBufferProcess(
    cameras=cameras,
    host_name=ARGS.host_name,
    port=ARGS.port,
    Q_maxsize=ARGS.queue_length)

video_params = VideoParameters(
    save_path=ARGS.output_path,
    fps=ARGS.fps, seconds=ARGS.seconds, codec="mp4v")

write_videos_from_video_stream(mcsb, video_params)
