import subprocess
import degirum as dg
import sys
import logging
import json
import os

# Dynamically get the user's home directory
HOME_DIR = os.path.expanduser("~")
LOG_PATH = os.path.join(HOME_DIR, "system-status.log")
JSON_PATH = os.path.join(HOME_DIR, "system-status.json")

# Configure logging
logging.basicConfig(
    filename=LOG_PATH,
    filemode='a',  # Append mode
    format='%(asctime)s %(levelname)s: %(message)s',
    level=logging.INFO
)

def log_status(status):
    logging.info(f"STATUS: {status}")
    write_status_json(status)

def write_status_json(status, json_path=JSON_PATH):
    data = {"STATUS": status}
    try:
        with open(json_path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logging.error(f"Failed to write status JSON: {e}")

def get_sys_info():
    try:
        # Run the CLI command and capture the output
        result = subprocess.run(
            ["degirum", "sys-info"], capture_output=True, text=True, check=True
        )
        logging.info(result.stdout)  # Log the command output
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing 'degirum sys-info': {e.stderr}")
        log_status("FAILED")
        write_status_json("FAILED")
        sys.exit(1)
    except FileNotFoundError:
        logging.error("Error: 'degirum' command not found. Make sure DeGirum PySDK is installed.")
        log_status("FAILED")
        write_status_json("FAILED")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error while getting system info: {e}")
        log_status("FAILED")
        write_status_json("FAILED")
        sys.exit(1)

if __name__ == "__main__":
    try:
        logging.info("System information:")
        get_sys_info()

        try:
            supported_devices = dg.get_supported_devices(inference_host_address="@local")
        except Exception as e:
            logging.error(f"Error fetching supported devices: {e}")
            log_status("FAILED")
            write_status_json("FAILED")
            sys.exit(1)

        logging.info(f"Supported RUNTIME/DEVICE combinations: {list(supported_devices)}")

        if "HAILORT/HAILO8L" in supported_devices:
            device_type = "HAILORT/HAILO8L"
        elif "HAILORT/HAILO8" in supported_devices:
            device_type = "HAILORT/HAILO8"
        else:
            logging.error("Hailo device is NOT supported or NOT recognized properly. Please check the installation.")
            log_status("FAILED")
            write_status_json("FAILED")
            sys.exit(1)

        logging.info(f"Using device type: {device_type}")
        logging.info("Running inference on Hailo device")

        inference_host_address = "@local"
        zoo_url = "./models/guard_detection_model"
        model_name = "guard_detection_model"
        image_source = "input/guard_1.png"

        try:
            model = dg.load_model(
                model_name=model_name,
                inference_host_address=inference_host_address,
                zoo_url=zoo_url,
                device_type=device_type,
            )
        except Exception as e:
            logging.error(f"Error loading model '{model_name}': {e}")
            log_status("FAILED")
            write_status_json("FAILED")
            sys.exit(1)

        logging.info(f"Running inference using '{model_name}' on image source '{image_source}'")
        try:
            inference_result = model(image_source)
            logging.info(f"Inference result: {inference_result}")
        except Exception as e:
            logging.error(f"Error during inference: {e}")
            log_status("FAILED")
            write_status_json("FAILED")
            sys.exit(1)

        # If reached here, inference was successful
        log_status("SYSTEM_READY")
        write_status_json("SYSTEM_READY")

    except KeyboardInterrupt:
        logging.warning("Process interrupted by user.")
        log_status("FAILED")
        write_status_json("FAILED")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        log_status("FAILED")    
        write_status_json("FAILED")
        sys.exit(1)
