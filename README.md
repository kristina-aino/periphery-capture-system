# camera-capture-system

## Description

A system that:
1) captures USB camera feeds using openCV with platform specific backends
2) syncronizes the video feeds and adds metadata
3) sends the resulting frame and metadata over a network connection using ZMQ PubSub

## Usage

### clone the repo and cd into it
```shell
git clone https://github.com/kristina-aino/camera-capture-system.git
cd camera-capture-system
```
### poetry setup, test and build
```shell
poetry install
poetry run pytest
poetry build
```
### create the config file for your camera setup
#### Example
> ```json
> {
>   "cam0": {
>     "id": 1,
>     "width": 1920,
>     "height": 1080,
>     "fps": 30,
>     "name": "A-webcam",
>     "position": "center"
>   },
>   "cam1": {
>     "id": 0,
>     "width": 1920,
>     "height": 1080,
>     "fps": 60,
>     "name": "Another-webcam",
>     "position": "center-right"
>   },
> }
> ```
> - "cam0", "cam1", etc. is considered the uuid and is required to be unique (enforced by json standard)
> - "id" is the OpenCV id the camera runs under 
> - "width", "height" and "fps" are camera specification
> - "name" and "position" are human redables with no logical value
### Start the capture and publishing on localhost port 10000
```shell
poetry run python main.py
```
### Or use it as a module
```python
from camera_capture_system.core import load_all_cameras_from_config, MultiCameraCaptureAndPublish

cameras = load_all_cameras_from_config(path_to_conf)

pccp = MultiCameraCaptureAndPublish(cameras=cameras)
pccp.start()

```

*(if there are problems, feel free to create an issue)*


## TODOs
- [ ] add a mode for Multi processing camera capture (collecting and sending should still be done on main thread)
- [ ] add a mode for Multi processing for both capture and sending
- [ ] add an option for sending video frames over dedicated sockets insetead over one
- [ ] upload the whl instead of manual build

