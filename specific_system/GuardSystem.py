import degirum as dg
import sys
import os
import time
import cv2
import json
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libraries.utils import mat_to_response, does_boxes_overlap_by, time_to_string
from libraries.utils import drawRectangle, drawText
from GeneralSystem import GeneralSystem
from collections import Counter

class GuardSystem(GeneralSystem):

    # Declaring global variable for holding each frame's guard count
    # This will be used by the judgment system to send the data to the server according to judgment interval
    detection_buffer = []
    inferred_frame_count_for_judgement = 0 # This will check how many frames have been processed so far and if it is exceeding judgment_nth_frame
    last_judgement_time = 0 # This will be used to check if the judgement interval has passed or not
    last_datasend_time = 0 # This will be used to check if the datasend interval has passed or not

    def __init__(self, config_path):
        super().__init__(config_path)
        self.timeline_data = [] # This will hold the data to be sent to the server
        self.timeline_image = []
        self.debug = self.config["debug"]
        
    
    def softmax(self, scores):
        # Handle empty arrays
        if len(scores) == 0:
            return np.array([])
        exp_scores = np.exp(scores - np.max(scores))
        return exp_scores / np.sum(exp_scores)

    def load_model_local(self):
        model_name = self.config["model_name"] # Guard Detection model
        zoo_url = self.config["zoo_url"]

        model_name_classification = self.config["model_name_classification"] # Guard Classification model
        zoo_url_classification = self.config["zoo_url_classification"]

        try:
            # Guard Detection model
            self.guard_detection_model = dg.load_model(
                 model_name = model_name, 
                inference_host_address = "@local",
                zoo_url = zoo_url,
                output_confidence_threshold=0.1,  # Adjust this value as needed (0.0 to 1.0)
                output_nms_threshold=0.7         # Adjust this value as needed (0.0 to 1.0)
            )

            # Guard Classification model
            self.guard_classification_model = dg.load_model( model_name = model_name_classification, inference_host_address = "@local", zoo_url = zoo_url_classification )

        except Exception as e:
            print(f"Error at loading models: {e} {self.strId}. Exiting program...")
            sys.exit(1)

    def classification_models_output_processing(self, inference_result):
        """
        Processing the output of the classification model to get the probabilty from scores.
        Args:
        inference_result: Raw inference result from regnetx classification model

        Example of classification model output:
        inference_result = {
            'results': [
                {'label': 'guard', 'score': 1.42, 'category_id': 0},
                {'label': 'not_guard', 'score': -3.33, 'category_id': 1}
            ]
        }

        Returns:
        list: Processed results with probabilities
        Example output:
        [
            {'label': 'guard', 'probability': 0.8, 'category_id': 0, raw_score: 1.42},
            {'label': 'not_guard', 'probability': 0.2, 'category_id': 1, raw_score: -3.33}
        ]
        """
        # Print Inference result for debugging
        # print(f"Inference result before processing: {inference_result}")

        # Check if we have 'results' attribute or if it's already a list
        if hasattr(inference_result, 'results'):
            results = inference_result.results
        else:
            results = inference_result
        
        # Handle empty results
        if not results:
            print("WARNING: Empty inference result detected in classification_models_output_processing")
            return []
        
        # Extract raw scores
        raw_scores = [result['score'] for result in results]
        
        # Convert to probabilities
        probabilities = self.softmax(raw_scores)
        
        # Create new processed results with probabilities
        processed_results = []
        for i, result in enumerate(results):
            processed_results.append({
                'label': result['label'],
                'probability': float(probabilities[i]),  # Convert to float for JSON serialization
                'category_id': result['category_id'],
                'raw_score': result['score']  # Keep original score for reference
            })

        # Print processed results for debugging
        # print(f"Processed results: {processed_results}")
        
        return processed_results
    
    def check_if_it_is_guard(self, inference_result):
        """
        Check if the classification result is guard or not.
        Args:
        inference_result: Processed inference result from classification model

        Returns:
        bool: True if it is guard, False otherwise
        """

        # Check if the inference is empty, meaning no gurad present in the frame
        if not inference_result:
            print("WARNING: Empty inference result in check_if_it_is_guard, Maybe no guard present in the frame")
            return False

        # Check if we have 'results' attribute or if it's already a list
        if hasattr(inference_result, 'results'):
            results = inference_result.results
        else:
            results = inference_result
        
        # Check if guard's probability >= not_guard's probability
        if results[0]['probability'] >= results[1]['probability']:
            return True
        else:
            return False
    
    def run_detection_and_classification(self, frame):
        frame = frame.copy()

        inference_result_guard_detection = self.guard_detection_model(frame)

        # Print Inference result len
        # print(f"Detection count before classification filter: {len(inference_result_guard_detection.results)}")

        # Logic from tanim bhai
        filtered_boxes, filtered_scores, filtered_classes = [], [], []

        # Extracting all guard boxes

        for item in inference_result_guard_detection.results:

            guard_box = item['bbox']

            xmin, ymin, xmax, ymax = int(guard_box[0]), int(guard_box[1]), int(guard_box[2]), int(guard_box[3])            

            # Extract the subimage from the frame
            cropped_guard_image = frame[int(guard_box[1]):int(guard_box[3]), int(guard_box[0]):int(guard_box[2])]

            # Run the guard classification model
            raw_classification_result = self.guard_classification_model(cropped_guard_image)

            # Process the classification model output for getting probabilities
            inference_result_guard_classification = self.classification_models_output_processing(raw_classification_result)
            """
            Example processed output
            [
                {'label': 'guard', 'probability': 0.8, 'category_id': 0, raw_score: 1.42},
                {'label': 'not_guard', 'probability': 0.2, 'category_id': 1, raw_score: -3.33}
            ]
            """
            # Check if it is actually guard or the detection is wrong
            is_it_really_guard = self.check_if_it_is_guard(inference_result_guard_classification)

            if is_it_really_guard:
                # If it is guard, then add the box to filtered boxes
                filtered_boxes.append(guard_box) # [xmin, ymin, xmax, ymax]
                filtered_scores.append(item['score']) # confidence score
                filtered_classes.append(item['category_id']) # 0 for guard, 1 for not_guard
            
        # print(f"after clssification filter: len(filtered_boxes)={len(filtered_boxes)}")
        
        return filtered_boxes, filtered_scores, filtered_classes, frame

    def guard_count_after_an_interval(self, current_time, frame_to_display_or_stream):
        # Judgement System State
        frames_to_decide = self.config['frames_to_decide']
        judgement_interval = self.config['judgement_interval']
        judge_every_nth_frame = max(1, self.config['judge_every_nth_frame'])
        
        # --- Judgement System Logic ---
        if GuardSystem.inferred_frame_count_for_judgement % judge_every_nth_frame == 0:
            GuardSystem.detection_buffer.append({
                "frame": frame_to_display_or_stream.copy(),
                "guard_count": self.guard_count_this_frame, # Store the count of confirmed guards
                "timestamp": current_time,
            })

        if len(GuardSystem.detection_buffer) >= frames_to_decide or current_time - GuardSystem.last_judgement_time >= judgement_interval:
            judgement_batch = GuardSystem.detection_buffer[-frames_to_decide:]
            guard_counts_in_batch = [item["guard_count"] for item in judgement_batch]

            if guard_counts_in_batch:
                count_mode = Counter(guard_counts_in_batch).most_common(1)[0][0]
            else:
                count_mode = 0

            final_present = count_mode > 0
            final_count = count_mode # The mode count of confirmed guards

            print(f"Judgement: Counts={guard_counts_in_batch} -> Mode={final_count}. Decision: Present={final_present}")

            frame_data_for_timeline = None
            send_frame_flag = final_present or self.config['always_send_frames']
            if send_frame_flag:
                found_frame = False
                for item in reversed(judgement_batch):
                    if item["guard_count"] == final_count:
                        frame_data_for_timeline = item["frame"]
                        found_frame = True
                        break
                if not found_frame and judgement_batch:
                    frame_data_for_timeline = judgement_batch[-1]["frame"]

                # Updating the timeline data
                self.timeline_data.append({
                    "sn": self.config['sn'],
                    "present": final_present,
                    "guard_count": final_count, # Store the mode count
                    "start_time": time_to_string(judgement_batch[0]["timestamp"]),
                    "end_time": time_to_string(judgement_batch[-1]["timestamp"])
                    # "image_data": frame_data_for_timeline
                })

                if self.debug:
                    print (f"Timeline data: {self.timeline_data}")

                self.timeline_image.append( {"image": mat_to_response(frame_data_for_timeline) } )

                GuardSystem.detection_buffer = []
                GuardSystem.last_judgement_time = current_time
                GuardSystem.inferred_frame_count_for_judgement = 0

        return None

    def runModel(self, frame, frameNo):
        """
        Run the model on the garbage, and person frame. Then merge the results to prevent false garbage detection in person frame.
        It will make a copy of the frame to avoid modifying the original one.
        """
        processing_started_time = time.time()
        frame = frame.copy()

        # Set Datasend Interval - 1 min        
        current_time = time.time()

        # NEED TO UPDATE HERE --> currently thinking of sending it timeline_data to generate_data
        # if use_judgement and (current_time - self.last_datasend_time >= self.datasend_interval):
        #     if send_timeline_data(timeline_data, config, uploader):
        #         timeline_data = []
        #         last_datasend_time = current_time


        # Run the guard detection and classification
        filtered_boxes, filtered_scores, filtered_classes, frame = self.run_detection_and_classification(frame)

        # Print for debugging
        # print(f"Filtered boxes: {filtered_boxes}")
        # print(f"Filtered scores: {filtered_scores}")
        # print(f"Filtered classes: {filtered_classes}")

        # Count represents the number of confirmed guards found
        self.guard_count_this_frame = len(filtered_boxes)
        frame_to_display_or_stream = frame.copy()

        if filtered_boxes:  # Only draw if there are boxes
            for i, box in enumerate(filtered_boxes):
                drawRectangle(self.debug, frame_to_display_or_stream, box[0], box[1], box[2], box[3], color=(0, 255, 0), thickness=2)
                drawText(self.debug, frame_to_display_or_stream, "Guard", box[0], box[1], color=(55, 255, 0), fontScale=0.7, thickness=2)


        # Incrementing the inferred frame count for judgement
        GuardSystem.inferred_frame_count_for_judgement += 1

        # Applying the judgement system
        # Judgment system handles the logic of sending data to the server according to the judgement interval
        # Judgment system updates the last_judgement_time and resets the inferred frame count for judgement
        self.guard_count_after_an_interval(current_time, frame_to_display_or_stream) # returns nothing 

        processing_time = time.time() - processing_started_time
        cv2.putText(frame_to_display_or_stream, f"Frame No: {frameNo}, Guard Count this frame: {self.guard_count_this_frame}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)        

        self.last_annotated_frame = frame_to_display_or_stream

        return frame_to_display_or_stream, processing_time*1000

    def generate_data(self, start_time, end_time):
        """
        timeline data structure
        [
            {
                "sn": "guard1",
                "present": True,
                "guard_count": 5,
                "start_time": "2023-10-01 12:00:00",
                "end_time": "2023-10-01 12:01:00",
            },
            ...
        ]
        """

        return self.timeline_data, self.timeline_image
