import argparse
import sys

from periphery_capture_system.deviceIO import get_all_devices_ffmpeg, save_periphery_devices_to_config

if __name__ == "__main__":

    AP = argparse.ArgumentParser()
    AP.add_argument("-p", "--print_devices", action="store_true", help="print devices to console")
    AP.add_argument("-v", "--verbose", action="store_true", help="print debug messages")
    AP.add_argument("-s", "--save_devices", action="store_true", help="save devices to config")
    AP.add_argument("-o", "--output_path", type=str, default=None, help="output path")
    ARGS = AP.parse_args()
    
    if len(sys.argv) == 1:
        AP.print_help(sys.stderr)
        sys.exit(1)
    
    # ---------------------------------------------------------------------
    
    devices = get_all_devices_ffmpeg()
    
    if ARGS.print_devices:
        
        print("Video Devices:\n")
        for video_device in [dev for dev in devices if dev.device_type == "video"]:
            if ARGS.verbose:
                print("\t", video_device.name, " : ", video_device.device_id)
            else:
                print("\t", video_device.name)
        
        print("\nAudio Devices:\n")
        for audio_device in [dev for dev in devices if dev.device_type == "audio"]:
            if ARGS.verbose:
                print("\t", audio_device.name, " : ", audio_device.device_id)
            else:
                print("\t", audio_device.name)
    
    if ARGS.save_devices:
        assert ARGS.output_path is not None, "output path must be provided"
        assert ARGS.output_path.endswith(".json"), "output path must be a json file"
        save_periphery_devices_to_config(devices, ARGS.output_path)