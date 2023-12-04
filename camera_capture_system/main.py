import json
from typing import List
import argparse

from . import Camera

# ---------------------------------------------------------------------

AP = argparse.ArgumentParser()
AP.add_argument("-c", "--config", default="./camera_configs.json", help="path to input configuration file")
AP.add_argumunt("-h", "--host", type=str, default="172.0.0.1", help="host ip of the server")
AP.add_argument("-", "--", type=int, default=, help="")
AP.add_argument("--port_range", default=[1024, 65534], help="port range to pick from for hosting the camera stream")
AP.add_argument("-d", "--debug", type=bool, default=False, help="debug mode")
ARGS = AP.parse_args()

# ---------------------------------------------------------------------





# ---------------------------------------------------------------------

def run():
    pass
    
    

# Setp 1: read camera configurations for all cameras

configurations = json.load(open("./cameras.json", "r"))
print(configurations)


# Step 2: argparse to call a package from cli


# Stup 3: pydantic + fastapi for exposing the camera configurations