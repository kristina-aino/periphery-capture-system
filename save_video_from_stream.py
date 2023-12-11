import argparse
import logging
import argparse

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("-cc", "--cameras_config", type=str, default="./cameras_configs.json", help="path to input configuration file")
AP.add_argument("-hn", "--host_name", type=str, default="127.0.0.1", help="host name or ip of the server")
AP.add_argument("-p", "--ports", nargs="+", default=[10000, 10001, 10002], help="port to opsn zmq socket on")

AP.add_argument("-op", "--output_path", type=str, required=True, help="output path")
AP.add_argument("--fps", type=int, default=30, help="fps of the output video (usually the same as the cameras)")
AP.add_argument("--seconds", type=int, default=10, help="number of seconds in the output video")

AP.add_argument("-ll", "--logging_level", type=str, default="info", help="logging level", choices=["debug", "warning", "error"])
ARGS = AP.parse_args()

# ---------------------------------------------------------------------

logging.basicConfig(level=ARGS.logging_level.upper())

# ---------------------------------------------------------------------

from camera_capture_system.core import load_all_cameras_from_config, MultiCameraZMQSubscriber
from camera_capture_system.fileIO import write_videos_from_zmq_stream
from camera_capture_system.datamodel import VideoParameters

if __name__ == "__main__":
    cameras = load_all_cameras_from_config(ARGS.cameras_config)
    mcsb = MultiCameraZMQSubscriber(
        cameras=cameras,
        host_name=ARGS.host_name,
        port=ARGS.ports)

    video_params = VideoParameters(
        save_path=ARGS.output_path,
        fps=ARGS.fps, seconds=ARGS.seconds, codec="mp4v")

    write_videos_from_zmq_stream(mcsb, video_params)
