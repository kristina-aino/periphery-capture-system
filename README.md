# Device Capture System

## Description

A simple system to capture ffmpeg input devices (cameras and microphones), **currently only using dshow-capture on windows**.

## Environment Setup
### 1) clone the repo and cd into directory
```shell
git clone https://github.com/kristina-aino/device-capture-system
cd device-capture-system
```
---
### 2) poetry setup, test and build
- activate an environment that has `poetry` installed.
```shell
poetry install
poetry run python -m pytest
```

## Device Setup
### 1) Pull All Devices through `ffmpeg`
- make sure to have `ffmpeg` installed
- `ffmpeg` should be available to the commandline inside the project
#### Print all devices to check
```shell
poetry run python ./device_helper.py -p
```
#### Save all devices in raw format to `./configs/raw_devices.json` (or any other directory)
```shell
poetry run python ./device_helper.py -s -o ./configs/raw_devices.json
```
#### Example raw device list produced by `device_helper`
```json
[
    {
        "device_id": "@device_pnp_\\\\?\\usb#vid_046d&pid_0893&mi_00#6&dc72295&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\\global",
        "name": "Logitech StreamCam",
        "device_type": "video"
    },
    {
        "device_id": "@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\\wave_{BA043884-E5A5-4D31-BA09-A26EEBB846D1}",
        "name": "Microphone (Arctis 7+)",
        "device_type": "audio"
    }
]
```
---
### 2) Add information to the devices depending on your hardware specification selection
- Im storing these in `./configs/devices.json`
- add information abuot capture `width`, `height` and capture `fps` to your camera devices
- add `channels`, `sample rate`, `sample size` in bits and `audio buffer size` to the audio devices
#### Example of `devices.json`
```json
[
  {
    "device_id": "@device_pnp_\\\\?\\usb#vid_046d&pid_0893&mi_00#6&dc72295&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\\global",
    "name": "Logitech-StreamCam.center",
    "device_type": "video",
    "width": 1920,
    "height": 1080,
    "fps": 30
  },
  {
    "device_id": "@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\\wave_{BA043884-E5A5-4D31-BA09-A26EEBB846D1}",
    "name": "Microphone (Arctis 7+)",
    "device_type": "audio",
    "channels": 1,
    "sample_rate": 88200,
    "sample_size": 16,
    "audio_buffer_size": 20
  }
]
```
- you can find this information by running the following command: ( insert `device_id` or `name` from above into the brackets {} )
```shell
ffmpeg -f dshow -list_options true -i video="{device_id}"
```

## Usage
### Test the video stream
```shell
poetry run python ./test_video_stream.py --num_frames 600
```
### Test the audio stream
```shell
poetry run python ./test_audio_stream.py
```
### Save a video
```shell
poetry run python ./save_video.py --output_path ./saved_videos/
```
### Save some images
```shell
poetry run python ./save_images.py --output_path ./saved_images/ --num_images 100
```
