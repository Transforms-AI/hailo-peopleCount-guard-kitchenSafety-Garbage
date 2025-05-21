import degirum as dg
import sys
import os
import cv2
import json
import numpy as np
import time
import psutil
import traceback
from time import sleep
from libraries.utils import time_to_string
from libraries.stream_publisher import StreamPublisher
from libraries.stream_receiver import StreamReceiver
from libraries.datasend import DataUploader
from libraries.async_capture import VideoCaptureAsync

# from emulator.emu_utils import generate_image

class GeneralSystem:
    def __init__(self, config_path):
        self.config = self.read_config(config_path)

        self.strId = self.config["name"]
        video_source = self.config["video_source"]
        #video_source = self.config["video_source_rename_later"]
        self.cap_async = VideoCaptureAsync(video_source)

        self.load_model_local() # in child class

        self.sn = self.config["sn"]
        self.local_ip = self.config["local_ip"]
        self.heartbeat_interval = self.config["heartbeat_interval"]
        self.datasend_interval = self.config['datasend_interval']
        self.inference_interval = self.config['inference_interval']
        self.livestream = self.config["livestream"]
        self.show = self.config["show"]
        self.port = self.config["port"]

        # open a text file for logging
        file_path = f"output/{self.strId}/result.txt"
        # create the directory if it doesn't exist
        if not os.path.exists(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))

        self.log_file = open(file_path, "a")
        print(f"Logging to {file_path}")
        print(f"Starting detector with SN: {self.sn} and local IP: {self.local_ip} with port: {self.port}")

        self.streamer = StreamPublisher( "live_" + self.sn, start_stream = False, host = self.local_ip, port = self.port )

        # Initialize data uploader
        api_url = self.config['data_send_url']
        heartbeat_url = self.config['heartbeat_url']
        headers = {"X-Secret-Key": self.config["X-Secret-Key"]}
        self.data_uploader = DataUploader(api_url, heartbeat_url, headers)

    def start_operation(self):
        self.cap_async.start()
        if self.config['livestream']:
            self.streamer.start_streaming()
            print(f"Starting live stream on {self.strId}:{self.port}")

        # Initialize counter and timers
        frame_count = 0
        last_datasend_time = time.time()
        last_heartbeat_time = time.time()
        last_inference_time = time.time()
        last_frame_sent_time = time.time()
        loop_start_time = time.time()
        total_time = 0

        first_time = True
        summary = "--------------------------------------------------------------------\n"
        summary += f"Started at {time_to_string(time.time())} for {self.strId}\n"

        total_cpu = 0
        total_memory = 0
        trigger_count = 0
        fps_log = True
        process = psutil.Process()
        process.cpu_percent(interval=None)

        try:
            while True:
                iteration_start_time = time.time()
                ret, frame = self.cap_async.read()
                
                if not ret:
                    print(f"Error: Could not read frame {self.strId}")
                    sleep(0.1)
                    continue
                
                # Resizing the frame to 640x480 here, gives better result.
                frame = cv2.resize(frame, (640, 480)) # (width, height)

                if first_time:
                    last_datasend_time = time.time()
                    last_heartbeat_time = time.time()
                    last_inference_time = time.time()
                    last_frame_sent_time = time.time()
                    loop_start_time = time.time()

                    total_time = 0
                    first_time = False

                    # save frame
                    # outptut_path = f"output/{self.strId}/first_frame_final.jpg"
                    # cv2.imwrite(outptut_path, frame)

                current_time = time.time()
                
                # Send Heartbeat
                if fps_log and (current_time - last_heartbeat_time >= self.heartbeat_interval):
                    hearbeat_time = time.time()
                    self.data_uploader.send_heartbeat( self.sn, self.local_ip, time_to_string(current_time) )
                    last_heartbeat_time = current_time
                    if frame_count % 20 == 0:
                        print(f"Heartbeat: {frame_count} took: {(time.time() - hearbeat_time)*1000:.2f} ms")

                # Perform inference every 'inference_interval' seconds
                if current_time - last_inference_time < self.inference_interval:
                    continue
                
                annotated_frame, processing_time = self.runModel(frame, frame_count)
                #sys.exit(0) # for testing

                if frame_count > 100 and frame_count % 50 == 0:
                    folder_path = f"output/{self.strId}"
                    # create the directory if it doesn't exist
                    if not os.path.exists(folder_path):
                        os.makedirs(folder_path)

                    output_path = f"output/{self.strId}/frame_{frame_count}.jpg"
                    print(f"Saved at {output_path}")
                    cv2.imwrite(output_path, annotated_frame)

                total_time += processing_time
                if frame_count == 0: # ignoring the first inference, as it is taking much time
                    total_time = 0
                
                # Send live stream data
                if fps_log and self.livestream:
                    #if (time.time() - last_frame_sent_time) >= .1:
                    last_frame_sent_time = time.time()
                    # print size of annotated_frame
                    size_mb = frame.nbytes / (1024*1024)  # Size in KB
                    frame_sent_start_time = time.time()

                    #dummy_frame = generate_image(frame_count % 2)
                    self.streamer.updateFrame(annotated_frame)
                    # self.streamer.updateFrame(dummy_frame)
                    if frame_count % 20 == 0:
                        print(f"Frame:{frame_count} Size: {size_mb:.2f}mb, took: {((time.time() - frame_sent_start_time)*1000):.2f} ms")
                    #print(f"Frame {frame_count} sent to live stream {self.strId}")
                frame_count += 1

                time_so_far = (time.time() - loop_start_time)
                fps = frame_count / (total_time/1000) if total_time > 0 else 0
                # print(f"FPS: {fps:.2f}, total time: {total_time:.2f} ms, frame count: {frame_count} for {self.strId}")
                
                if fps_log and (frame_count % 20 == 0):
                    #cpu = psutil.cpu_percent(interval=.1)  # CPU usage in %
                    memory = psutil.virtual_memory().percent  # RAM usage in %

                    #total_cpu += cpu
                    total_memory += memory
                    trigger_count += 1

                    print(f"Frame no: {frame_count} at {self.strId} avg fps: {fps:.2f} and memory: {memory:.2f}%")
                    summary += f"Frame no: {frame_count} processed in {processing_time:.2f} ms with avg fps {fps:.2f} and memory: {memory}%\n"

                if(frame_count >= 6000):
                    summary += f"Total {frame_count} frames processed.\n\n"
                    summary += f" Total time taken {total_time:.2f} ms.\n"
                    summary += f" Average FPS: {fps:.2f}\n"
                    summary += f"Average processing time: {total_time/frame_count:.2f} ms\n"

                    avg_cpu = total_cpu / trigger_count
                    avg_memory = total_memory / trigger_count
                    summary += f"Average CPU usage: {avg_cpu:.2f}%\n"
                    summary += f"Average Memory usage: {avg_memory:.2f}%\n"
                    summary += "--------------------------------------------------------------------\n\n"
                    self.log_file.write(summary)
                    self.log_file.flush()
                    break
                
                if fps_log and (time.time() - last_datasend_time >=  self.datasend_interval):
                    start_time = time_to_string(last_datasend_time)
                    end_time = time_to_string(current_time)
                    data_send_start_time = time.time()
                    
                    # generating data
                    data, files = self.generate_data(start_time, end_time)

                    # Prepare data for sending
                    for i in range(len(data)):
                        if files is None:
                            self.data_uploader.send_data(data[i])
                            print(f"Data sent: {frame_count} took: {(time.time() - data_send_start_time)*1000:.2f} ms. \n data: {data[i]}")
                        else:
                            self.data_uploader.send_data(data[i], files=files[i]) 
                            print(f"Data sent: {frame_count} took: {(time.time() - data_send_start_time)*1000:.2f} ms. \n data: {data[i]}")                                    

                    
                    last_datasend_time = time.time()
                
                if self.show:
                    cv2.namedWindow("Output", cv2.WINDOW_NORMAL)
                    cv2.imshow("Output", frame)
                    key = cv2.waitKey(1)
                    if key == 27:
                        break
                
                it_time = (time.time() - iteration_start_time)
                if frame_count % 20 == 0:
                    print(f"Iteration:{frame_count}, Infer: {processing_time}, Total: {(it_time*1000):.2f} ms")

                last_inference_time = current_time
                #sleep(0.5)
            # outside the loop
            cpu_usage = process.cpu_percent(interval=None)
            print(f"CPU usage: {cpu_usage:.2f}%")
        except Exception as e:
            print(f"Error during inference: {e} {self.strId}")
            traceback.print_exc()
            sys.exit(1)
    def generate_data(self, start_time, end_time):
        raise NotImplementedError("generate_data() must be implemented in the child class.")
    
    def read_config(self, file_path="config.json"):
        with open(file_path, "r") as f:
            config = json.load(f)
        return config

    def runModel(self, frame, frameNo):
        raise NotImplementedError("runModel() must be implemented in the child class.")

    def load_model_local(self):
        raise NotImplementedError("load_model_local() must be implemented in the child class.")
