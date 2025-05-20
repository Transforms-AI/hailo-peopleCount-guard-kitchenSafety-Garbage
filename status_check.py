import subprocess
import json
import argparse

def get_status_from_rpi(rpi_hostname, json_path="/home/admin/system-status.json", local_filename="system-status.json"):
    """
    Copies system-status.json from Raspberry Pi, reads it, and returns the status.
    """

    try:
        # SCP command to copy the file
        scp_command = f"scp {rpi_hostname}:{json_path} ."
        subprocess.run(scp_command, check=True, capture_output=True, text=True, shell=True)


        # Read and parse the JSON file
        with open(local_filename, 'r') as f:
            data = json.load(f)
            status = data.get("STATUS")

        return status

    except subprocess.CalledProcessError as e:
        print(f"Error copying file: {e.stderr}")
        return None
    except FileNotFoundError:
        print(f"Error: {local_filename} not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {local_filename}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

if __name__ == "__main__":
    # Replace with your Raspberry Pi username and IP address
    parser = argparse.ArgumentParser(description='Check Raspberry Pi system status')
    parser.add_argument('hostname', help='Raspberry Pi hostname, like rpi1001 or rpi1002 ...')
    args = parser.parse_args()
    
    RPI_HOSTNAME = args.hostname

    status = get_status_from_rpi(RPI_HOSTNAME)

    if status == "SYSTEM_READY" or status == "FAILED":
        print(f"System status on Raspberry Pi {RPI_HOSTNAME}: {status}")
    else:
        print(f"Could not retrieve system status from Raspberry Pi {RPI_HOSTNAME}.")
