import degirum as dg
import sys
import os
import time
import cv2
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libraries.utils import mat_to_response, does_boxes_overlap_by

from GeneralSystem import GeneralSystem

class SafetySystem(GeneralSystem):
    def __init__(self, config_path):
        super().__init__(config_path)

    def load_model_local(self):
        model_name = self.config["model_name"] # primary model
        zoo_url = self.config["zoo_url"]

        model_name_person = self.config["model_name_person"] # person model
        zoo_url_person = self.config["zoo_url_person"]

        try:
            # Garbage model
            self.safety_model = dg.load_model( model_name = model_name, inference_host_address = "@local", zoo_url = zoo_url )

            # Person model
            self.person_model = dg.load_model( model_name = model_name_person, inference_host_address = "@local", zoo_url = zoo_url_person )
        except Exception as e:
            print(f"Error at loading models: {e} {self.strId}. Exiting program...")
            sys.exit(1)

    def runModel(self, frame, frameNo):
        """
        Run the model on the safety, and person frame. Then merge the results to generate annotated image and vialation list.
        It will make a copy of the frame to avoid modifying the original one.
        """

        processing_started_time = time.time()
        frame = frame.copy()

        inference_result_safety = self.safety_model(frame)
        inference_result_person = self.person_model(frame)
        
        inference_time = time.time() - processing_started_time

        person_related_class_id = [0, 1, 2, 3, 4, 5, 8, 10]
        violation_classes_id = [1, 3, 5, 6, 9, 10]

        filtered_boxes = []
        violation_list = []

        for box in inference_result_safety.results:
            # print(box)
            if box['category_id'] not in person_related_class_id: # not person related. Add directly
                filtered_boxes.append(box)
                if box['category_id'] in violation_classes_id:
                    violation_list.append(box)
            else:
                # check if it overlaps with person. If overlaps, take it
                if any(does_boxes_overlap_by(box['bbox'], person_box['bbox'], by=0.8) for person_box in inference_result_person.results):
                    filtered_boxes.append(box)
                    if box['category_id'] in violation_classes_id:
                        violation_list.append(box['label'])

        # Annotate the frame with the filtered boxes
        for box in filtered_boxes:
            x1, y1, x2, y2 = box['bbox']
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            # cv2.putText(frame, f"{box['category_id']}", (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        processing_time = time.time() - processing_started_time
        cv2.putText(frame, f"Frame No: {frameNo}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        self.last_violation_list = violation_list
        self.last_annotated_frame = frame

        # print(f"Exiting forcely to test the system {self.strId}")
        # sys.exit(0) # exit the process for testing purposes
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
