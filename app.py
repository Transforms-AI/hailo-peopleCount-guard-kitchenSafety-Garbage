import subprocess
import degirum as dg
import sys
import cv2
import time
import json
from time import sleep
from libraries.utils import time_to_string, mat_to_response
from libraries.stream_publisher import StreamPublisher
from libraries.stream_receiver import StreamReceiver
from libraries.datasend import DataUploader
from libraries.async_capture import VideoCaptureAsync

def initialize_config():
    global config, streamer, frame_count, last_datasend_time, last_heartbeat_time, last_inference_time, api_url, heartbeat_url, headers, data_uploader

    with open("config.json", "r") as f:
        config = json.load(f)
    
    if config['livestream']:
        streamer = StreamPublisher( "live_" + config['sn'], start_stream=False, host=config['local_ip'], port=1883, jpeg_quality=70, target_width=1600 )
        streamer.start_streaming()
        # Initialize counter and timers
    
    frame_count = 0
    last_datasend_time = time.time()
    last_heartbeat_time = time.time()
    last_inference_time = time.time()

    # Initialize DataUploader
    api_url = config['data_send_url']
    heartbeat_url = config['heartbeat_url']
    headers = {"X-Secret-Key": config["X-Secret-Key"]}
    data_uploader = DataUploader(api_url, heartbeat_url, headers)

def inspect_available_attributes(obj):
    """
    Print detailed information about an obj object.
    
    Args:
        obj: The inference result object from degirum_tools
    """
    
    # Get type information
    print(f"Type: {type(obj)}")
    print()
    
    # Get all attributes and methods
    print("Attributes and Methods:")
    for attr in dir(obj):
        # Skip private/protected attributes (starting with _)
        if not attr.startswith('_'):
            try:
                value = getattr(obj, attr)
                # Check if it's a method or an attribute
                if callable(value):
                    print(f"  - {attr}(): method")
                else:
                    # Try to get the type and a preview of the value
                    value_type = type(value).__name__
                    
                    # For lists, tuples, dicts, show length and a preview
                    if isinstance(value, (list, tuple)):
                        preview = f"{value_type} with {len(value)} items"
                        if len(value) > 0:
                            first_item = value[0]
                            preview += f" (first item type: {type(first_item).__name__})"
                    elif isinstance(value, dict):
                        preview = f"{value_type} with {len(value)} keys: {', '.join(list(value.keys())[:3])}"
                        if len(value.keys()) > 3:
                            preview += ", ..."
                    else:
                        # Try to create a string representation, but limit its length
                        try:
                            str_val = str(value)
                            preview = str_val[:50]
                            if len(str_val) > 50:
                                preview += "..."
                        except:
                            preview = f"<{value_type} - cannot display>"
                    
                    print(f"  - {attr}: {preview}")
            except Exception as e:
                print(f"  - {attr}: <Error accessing: {e}>")
    
    print()
    print("=" * 50)


def runModel(model, frame):
    """
    Run the model on the given frame, then draw the bounding boxes and return the annotated frame.
    It will make a copy of the frame to avoid modifying the original one.
    """
    frame = frame.copy()

    inference_result = model(frame)
    
    for item in inference_result.results:
        bounding_box = item['bbox']
        
        # drawing bounding box on the frame
        xmin = int(bounding_box[0])
        ymin = int(bounding_box[1])
        xmax = int(bounding_box[2])
        ymax = int(bounding_box[3])
        
        cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
    
    return frame


def live():
    global modelPerson, modelGarbage, config

    #video_source = config["video_source"] # camera stream
    video_source = config["local_video_source"]
    cap_async = VideoCaptureAsync(video_source)
    cap_async.start()

    if config['livestream']:
        streamer = StreamPublisher( "live_" + config['sn'], start_stream=False, host=config['local_ip'], port=1883 )
        streamer.start_streaming()

    # Initialize counter and timers
    frame_count = 0
    last_datasend_time = time.time()
    last_heartbeat_time = time.time()
    last_inference_time = time.time()

    # Initialize DataUploader
    api_url = config['data_send_url']
    heartbeat_url = config['heartbeat_url']
    headers = {"X-Secret-Key": config["X-Secret-Key"]}
    data_uploader = DataUploader(api_url, heartbeat_url, headers)
    
    try:
        while True:
            ret, frame = cap_async.read()
            
            if not ret:
                print("Error: Could not read frame.")
                sleep(0.1)
                continue

            frame_count += 1
            current_time = time.time()
            # Send Heartbeat
            if current_time - last_heartbeat_time >= config["heartbeat_interval"]:
                data_uploader.send_heartbeat( config["sn"], config["local_ip"], time_to_string(current_time) )
                last_heartbeat_time = current_time

            # Perform inference every 'inference_interval' seconds
            if current_time - last_inference_time < config["inference_interval"]:
                continue
            
            annotated_frame_person = runModel(modelPerson, frame)
            annotated_frame_garbage = runModel(modelGarbage, frame)

            # save the annotated frame with frame count
            # cv2.imwrite("output/person/annotated_frame_person{}.jpg".format(frame_count), annotated_frame_person)
            # cv2.imwrite("output/garbage/annotated_frame_garbage{}.jpg".format(frame_count), annotated_frame_garbage)

            # if count > 10:
            #     sys.exit(1)
            # count += 1
            
            # print("Inference completed successfully.")
            # print("Person Inference Result:", inference_resultPerons)
            # print("Garbage Inference Result:", inference_resultGarbage)
            
            if time.time() - last_datasend_time >= config['datasend_interval']:
                start_time = time_to_string(last_datasend_time)
                end_time = time_to_string(current_time)
                
                # Prepare data for sending
                data = {
                    "sn": config['sn'],
                    "violation_list": json.dumps([]),#violation_list),
                    "violation": False, #True if len(violation_list) != 0 else False,
                    "start_time": start_time,
                    "end_time": end_time
                }

                # Prepare files for sending
                files = {"image": mat_to_response(frame)}

                # Send data with image
                data_uploader.send_data(data, files=files)
                last_datasend_time = time.time()
            
            # Send live stream data
            if config['livestream']:
                streamer.updateFrame(frame)
                print(f"Frame {frame_count} sent to live stream.")
            
            if config["show"]:
                cv2.namedWindow("Output", cv2.WINDOW_NORMAL)
                cv2.imshow("Output", frame)
                key = cv2.waitKey(1)
                if key == 27:
                    break
                
            last_inference_time = current_time
            sleep(1)
    except Exception as e:
        print(f"Error during inference: {e}")
        sys.exit(1)

if __name__ == "__main__":

    try:
        initialize_config()
        print("Configuration initialized successfully.")

        device_type = "HAILORT/HAILO8"
        inference_host_address = "@local"
        zoo_url = "degirum/hailo"
        token = ""

        image_source = "assets/ThreePersons.jpg"

        # Load AI model
        try:
            global modelPerson, modelGarbage

            modelPerson = dg.load_model(
                model_name = "yolov8n_relu6_coco--640x640_quant_hailort_hailo8l_1",
                inference_host_address = inference_host_address,
                zoo_url = zoo_url,
                token = token,
                device_type = device_type,
            )
            modelGarbage = dg.load_model(
                #model_name = "yolov8n_relu6_coco--640x640_quant_hailort_hailo8_1",
                model_name = "garbage_detection_model",
                inference_host_address = '@local',
                zoo_url = './models/garbage_detection_model',
                #zoo_url = './models/yolov8n_relu6_coco--640x640_quant_hailort_hailo8_1',
                # token = token,
                # device_type = device_type,
            )
            live()
        except Exception as e:
            print(f"Error at loading models: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
