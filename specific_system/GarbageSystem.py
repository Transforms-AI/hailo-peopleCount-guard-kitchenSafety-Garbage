import degirum as dg
import sys
import os
import time
import cv2
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libraries.utils import mat_to_response, does_boxes_overlap_by

from GeneralSystem import GeneralSystem

class GarbageSystem(GeneralSystem):
    def __init__(self, config_path):
        super().__init__(config_path)

    def load_model_local(self):
        model_name = self.config["model_name"] # primary model
        zoo_url = self.config["zoo_url"]

        model_name_person = self.config["model_name_person"] # person model
        zoo_url_person = self.config["zoo_url_person"]

        try:
            # Garbage model
            self.garbage_model = dg.load_model( model_name = model_name, inference_host_address = "@local", zoo_url = zoo_url )

            # Person model
            self.person_model = dg.load_model( model_name = model_name_person, inference_host_address = "@local", zoo_url = zoo_url_person )
        except Exception as e:
            print(f"Error at loading models: {e} {self.strId}. Exiting program...")
            sys.exit(1)

    def runModel(self, frame, frameNo):
        """
        Run the model on the garbage, and person frame. Then merge the results to prevent false garbage detection in person frame.
        It will make a copy of the frame to avoid modifying the original one.
        """

        processing_started_time = time.time()
        frame = frame.copy()

        inference_result_garbage = self.garbage_model(frame)
        inference_result_person = self.person_model(frame)
        
        inference_time = time.time() - processing_started_time

        # Extracting all person boxes
        person_boxes = []
        for item in inference_result_person.results:
            # {'bbox': [98.68952751159668, 451.9453430175781, 329.2456817626953, 640], 'category_id': 0, 'label': 'person', 'score': 0.7400065064430237}
            person_box = item['bbox']
            person_boxes.append(person_box)
            # person in red color
            # cv2.rectangle(frame, (int(person_box[0]), int(person_box[1])), (int(person_box[2]), int(person_box[3])), (255, 0, 0), 1)
        
        # Process garbage detections and draw only those that don't overlap with person
        for item in inference_result_garbage.results:
            garbage_box = item['bbox']
            
            # box in black color
            # cv2.rectangle(frame, (int(bounding_box[0]), int(bounding_box[1])), (int(bounding_box[2]), int(bounding_box[3])), (0, 0, 0), 1)
            
            # Check if overlaps
            overlaps_with_person = any(does_boxes_overlap_by(garbage_box, person_box) for person_box in person_boxes)
            
            if not overlaps_with_person: # no overlap
                cv2.rectangle( frame, 
                    (garbage_box[0], garbage_box[1]),  (garbage_box[2], garbage_box[3]),
                    (0, 255, 0), 2 # green
                )
        
        processing_time = time.time() - processing_started_time
        cv2.putText(frame, f"Frame No: {frameNo}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        self.last_violation_list = [] # empty for now
        self.last_annotated_frame = frame
        return frame, processing_time*1000

    def generate_data(self, start_time, end_time):
        data = {
            "sn": self.sn,
            "violation_list": json.dumps(self.last_violation_list),
            "violation": True if len(self.last_violation_list) != 0 else False,
            "start_time": start_time,
            "end_time": end_time
        }

        # Prepare files for sending
        files = {"image": mat_to_response(self.last_annotated_frame) }
        return data, files
