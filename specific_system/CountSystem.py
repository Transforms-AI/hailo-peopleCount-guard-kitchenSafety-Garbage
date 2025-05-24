import degirum as dg
import sys
import os
import time
import cv2
import json
import numpy as np
from boxmot import ByteTrack
import math
from collections import deque

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from libraries.utils import mat_to_response, does_boxes_overlap_by
from libraries.utils import drawCircle, drawRectangle, drawText, drawLine
from libraries.utils import time_to_string

from GeneralSystem import GeneralSystem

class CountSystem(GeneralSystem):
    def __init__(self, config_path):
        super().__init__(config_path)
        self.sn = self.config["sn"]
        self.debug = self.config["debug"]
        self.datasend_interval = self.config["datasend_interval"]
        self.head_count = HeadCount("./config/config_head_count.json", debug = self.debug, datasend_interval = self.datasend_interval, sn = self.sn)
        self.circular_buffer = CircularBuffer(amount_of_seconds=10)

    def load_model_local(self):
        model_name = self.config["model_name"] # primary model
        zoo_url = self.config["zoo_url"]

        try:
            self.person_model = dg.load_model(model_name = model_name, inference_host_address = "@local", zoo_url = zoo_url )
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

        # dummy_data = {
        #     "results":[
        #         {'bbox': [142, 209, 312, 583], 'category_id': 0, 'label': 'person', 'score': 0.7400065064430237},
        #         {'bbox': [438, 187, 605, 602], 'category_id': 0, 'label': 'person', 'score': 0.8923571109771729},
        #         {'bbox': [723, 197, 862, 569], 'category_id': 0, 'label': 'person', 'score': 0.9155387282371521},
        #         {'bbox': [28, 234, 138, 546], 'category_id': 0, 'label': 'person', 'score': 0.6783902645111084},
        #     ]
        # }
        
        inference_result_person = self.person_model(frame)
        time.sleep(0.05) # Simulate processing time
        
        inference_time = time.time() - processing_started_time
        
        preds = []
        # processing predictions preds -> List< [x1, y1, x2, y2, confidence, class_id] >
        for item in inference_result_person.results:
            person_box = item['bbox']
            # item: {'bbox': [xmin, ymin, xman, ymax], 'category_id': 0, 'label': 'person', 'score': 0.7400065064430237}
            one_pred = [ person_box[0], person_box[1], person_box[2], person_box[3], item['score'], item['category_id'] ]
            preds.append(one_pred)

        original_frame = self.head_count.process_frames(frame, preds)
        
        processing_time = time.time() - processing_started_time
        
        # cv2.putText(frame, f"Frame No: {frameNo}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        drawText(self.debug, original_frame, f"Frame No: {frameNo}", 10, 30, color=(0, 255, 0), fontScale=0.7, thickness=2)
        
        # self.circular_buffer.add(total_in, total_out)
        # total_in, total_out = self.circular_buffer.sum()
        
        # print(f"Frame No: {frameNo} - Total In: {total_in} - Total Out: {total_out} - Processing Time: {processing_time*1000:.2f} ms")
        
        self.last_annotated_frame = original_frame
        return frame, processing_time*1000

    def generate_data(self, start_time, end_time):
        if self.head_count.people_count_data is None:
            return [], None
        else:
            data = self.head_count.people_count_data
            self.head_count.people_count_data = [] # Clearing the data object
            return data, None

    def on_data_received(self, config_file): # overridden method
        self.head_count.update_settings(config_file)

class CircularBuffer:
    """
    A buffer that will store data of a certain period of time.
    """
    
    def __init__(self, amount_of_seconds=10):
        """
        Initialize the circular buffer with a specified time window.
        
        Args:
            amount_of_seconds (int): The time window in seconds to keep data.
                                    Defaults to 10 seconds.
        """
        self.amount_of_seconds = amount_of_seconds
        self._buffer = deque()
        
    def add(self, inn, out):
        """
        Add a value pair to the buffer with timestamp.
        
        Args:
            inn: The value of number of entering people
            out: The value of number of exiting people
        Returns:
            None
        """
        self._buffer.append((inn, out, time.time()))
    
    def sum(self):
        """
        Calculate the sum of all values in the buffer within the time window.
        Removes any entries older than the specified time window.
        
        Returns:
            tuple: (in_count, out_count) - The sums of entering and exiting people
                   within the time window.
        """
        in_count = out_count = 0
        current_time = time.time()
        cutoff_time = current_time - self.amount_of_seconds
        
        # Remove expired entries from the front of the deque
        while self._buffer and self._buffer[0][2] < cutoff_time:
            self._buffer.popleft()
        
        # Sum the remaining entries
        for inn, out, _ in self._buffer:
            in_count += inn
            out_count += out
        
        return in_count, out_count

class HeadCount:
    """
    Class for performing head counting using object detection and tracking.
    """

    def __init__(self, config_file='"./config/config_head_count.json"', debug=True, datasend_interval=10, sn="HEADCOUNT1"):
        """
        Initializes the HeadCount object.

        Args:
            config_file (str): Path to the configuration file.
        """
        self.config_file = config_file
        self.load_config()

        # Initialize frame dimensions and view dimensions
        self.width = self.config['width']
        self.height = self.config['height']
        self.view_width = self.config.get('view_width', self.width)
        self.view_height = self.config.get('view_height', self.height)

        # Initialize FPS calculation variables
        self.fps_start_time = time.time()
        self.frame_count = 0
        self.fps = 0

        # Initialize tracking variables
        self.persondown = {}
        self.counter1 = []
        self.personup = {}
        self.counter2 = []
        self.previous_midpoint_dict = {}
        self.idShowText = {}

        # Initialize object tracker
        self.tracker = ByteTrack()

        # Define entrance lines based on configuration
        self.entrance_lines = self.define_entrance_lines()

        # Initialize counters for entering and exiting people
        self.enter_count = 0
        self.exit_count = 0

        # Define tracking zone coordinates
        self.rectx1 = int(self.config['width'] * self.config['rx1'])
        self.recty1 = int(self.config['height'] * self.config['ry1'])
        self.rectx2 = int(self.config['width'] * self.config['rx2'])
        self.recty2 = int(self.config['height'] * self.config['ry2'])

        # Calculate line parameters for intersection checks
        self.l1y1 = int(self.config['height'] * self.config['l1y1'])
        self.l1y2 = int(self.config['height'] * self.config['l1y2'])
        self.l1dy = float(self.config['l1y2']) - float(self.config['l1y1'])
        self.l1constant = float(self.l1dy * self.height / self.width)

        self.l2y1 = int(self.config['height'] * self.config['l2y1'])
        self.l2y2 = int(self.config['height'] * self.config['l2y2'])
        self.l2dy = float(self.config['l2y2']) - float(self.config['l2y1'])
        self.l2constant = float(self.l2dy * self.height / self.width)

        # Define colors for visualization
        self.colorY = (0, 150, 150)
        self.colorG = (0, 155, 0)
        self.offset = 6
        
        # Debugging 
        self.debug = self.config.get('debug', True)
        self.datasend_interval = datasend_interval
        self.sn = sn
        self.color_default_line = (0, 255, 255) # Yellow for default lines (BGR)
        self.color_in = (0, 0, 255)             # Red for IN events (BGR)
        self.color_out = (255, 0, 0)            # Blue for OUT events (BGR)
        self.color_no_intersect = (255, 255, 0) # Cyan for movement without intersection
        self.color_min_dist = (255, 0, 255)     # Magenta for intersection failing min distance
        self.color_no_direction = (255, 255, 255) # White for intersection with 'none' direction
        self.debug_line_thickness = 2
        self.debug_lines = []

        # Initialize timing variables for data sending and heartbeat
        self.start_time = time.time()
        self.heartbeat_time = time.time()
        self.inSend = 0
        self.outSend = 0
        
        # Timed display variables
        self.display_timeout = 5.0 # Seconds
        self.last_event_time = 0.0
        self.display_enter_count = 0 # Counter for the current display period
        self.display_exit_count = 0  # Counter for the current display period
        self.show_display_counts = False # Flag to control drawing
        
        # Initialize tracking counting logic parameters
        self.min_movement_distance = 60
        self.line_cross_threshold = 30
        self.people_count_data = []
        
        
    def define_entrance_lines(self):
        """
        Defines the entrance lines based on the configuration.

        Returns:
            list: A list of tuples, where each tuple represents a line segment
                  ((x1, y1), (x2, y2)).
        """
        return [
            ((int(self.config['width'] * self.config['l1x1']), int(self.config['height'] * self.config['l1y1'])),
             (int(self.config['width'] * self.config['l1x2']), int(self.config['height'] * self.config['l1y2']))),
            ((int(self.config['width'] * self.config['l1x2']), int(self.config['height'] * self.config['l1y2'])),
             (int(self.config['width'] * self.config['l2x1']), int(self.config['height'] * self.config['l2y1']))),
            ((int(self.config['width'] * self.config['l2x1']), int(self.config['height'] * self.config['l2y1'])),
             (int(self.config['width'] * self.config['l2x2']), int(self.config['height'] * self.config['l2y2']))),
        ]

    def update_settings(self, config_file='"./config/config_head_count.json"'):
        """
        Updates the settings based on a new configuration file.

        Args:
            config_file (str): Path to the new configuration file.
        """
        print(f"Attempting to update settings using: {config_file}") # Added for debugging
        self.config_file = config_file
        self.load_config() # Loads the new config into self.config

        # --- Start of changes ---
        # Use .get() for robustness against missing keys in the loaded config
        print(f"Loaded config keys: {list(self.config.keys())}") # Added for debugging

        # Update frame dimensions and view dimensions
        self.width = self.config.get('width', 640) # Provide default if missing
        self.height = self.config.get('height', 360) # Provide default if missing
        self.view_width = self.config.get('view_width', self.width)
        self.view_height = self.config.get('view_height', self.height)

        # Update tracking zone coordinates (ensure defaults prevent errors if keys missing)
        self.rectx1 = int(self.width * self.config.get('rx1', 0.1))
        self.recty1 = int(self.height * self.config.get('ry1', 0.1))
        self.rectx2 = int(self.width * self.config.get('rx2', 0.9))
        self.recty2 = int(self.height * self.config.get('ry2', 0.9))

        # Update line parameters for intersection checks (ensure defaults prevent errors)
        self.l1y1 = int(self.height * self.config.get('l1y1', 0.4))
        self.l1y2 = int(self.height * self.config.get('l1y2', 0.4))
        self.l1dy = float(self.config.get('l1y2', 0.4)) - float(self.config.get('l1y1', 0.4))
        # Avoid division by zero if width is somehow 0
        self.l1constant = float(self.l1dy * self.height / self.width) if self.width else 0

        self.l2y1 = int(self.height * self.config.get('l2y1', 0.6))
        self.l2y2 = int(self.height * self.config.get('l2y2', 0.6))
        self.l2dy = float(self.config.get('l2y2', 0.6)) - float(self.config.get('l2y1', 0.6))
        # Avoid division by zero if width is somehow 0
        self.l2constant = float(self.l2dy * self.height / self.width) if self.width else 0

        # Update entrance lines (ensure defaults prevent errors)
        self.entrance_lines = self.define_entrance_lines() # This uses the updated config values

        print("Settings updated successfully.") # Confirmation message

    def load_config(self):
        """
        Loads the configuration from the JSON file.
        """
        print("Loading configuration from:", self.config_file)
        with open(self.config_file, 'r') as f:
            self.config = json.load(f)

    def points_to_line(self, x1, y1, x2, y2):
        """
        Calculates the coefficients of a line equation given two points.

        Args:
            x1 (float): x-coordinate of the first point.
            y1 (float): y-coordinate of the first point.
            x2 (float): x-coordinate of the second point.
            y2 (float): y-coordinate of the second point.

        Returns:
            tuple: The coefficients (a, b, c) of the line equation ax + by + c = 0.
        """
        a = y2 - y1
        b = x1 - x2
        c = a * x1 + b * y1
        return a, b, -c

    def intersect(self, segment1, segment2):
        """
        Checks if two line segments intersect.

        Args:
            segment1 (tuple): The first line segment ((x1, y1), (x2, y2)).
            segment2 (tuple): The second line segment ((x1, y1), (x2, y2)).

        Returns:
            str: "true" if the segments intersect and meet distance criteria,
                 "min_distance_not_meet" if they intersect but don't meet distance criteria,
                 "false" otherwise.
        """
        ax1, ay1, ax2, ay2 = segment1
        bx1, by1, bx2, by2 = segment2
        a1, b1, c1 = self.points_to_line(ax1, ay1, ax2, ay2)
        a2, b2, c2 = self.points_to_line(bx1, by1, bx2, by2)
        determinant = a1 * b2 - a2 * b1

        if determinant == 0:
            return "false"  # Parallel lines

        # Calculate intersection point
        x = abs(int((b2 * c1 - b1 * c2) / determinant))
        y = abs(int((a1 * c2 - a2 * c1) / determinant))

        # Check if intersection point is within both segments
        is_on_segment1 = min(ax1, ax2) <= x <= max(
            ax1, ax2) and min(ay1, ay2) <= y <= max(ay1, ay2)
        is_on_segment2 = min(bx1, bx2) <= x <= max(
            bx1, bx2) and min(by1, by2) <= y <= max(by1, by2)

        if is_on_segment1 and is_on_segment2:
            # Check minimum distance from intersection point to segment endpoints
            distance1 = abs(a2 * ax1 + b2 * ay1 + c2) / \
                math.sqrt(a2**2 + b2**2)
            distance2 = abs(a2 * ax2 + b2 * ay2 + c2) / \
                math.sqrt(a2**2 + b2**2)
            if distance1 < self.line_cross_threshold and distance2 < self.line_cross_threshold:
                return "min_distance_not_meet"
            return "true"
        else:
            return "false"

    def direction_of_movement(self, previous_midpoint, current_midpoint, line):
        """
        Determines the direction of movement relative to a line.

        Args:
            previous_midpoint (tuple): The previous midpoint (x, y).
            current_midpoint (tuple): The current midpoint (x, y).
            line (tuple): The line segment ((x1, y1), (x2, y2)).

        Returns:
            str: "entering" if moving towards the line, "exiting" if moving away,
                 "none" if no significant movement.
        """
        px, py = previous_midpoint
        cx, cy = current_midpoint
        movement_vector = (cx - px, cy - py)
        ax, ay, bx, by = line
        line_vector = (bx - ax, by - ay)
        cross_product = movement_vector[0] * \
            line_vector[1] - movement_vector[1] * line_vector[0]

        if cross_product > 0:
            return 'exiting'
        elif cross_product < 0:
            return 'entering'
        else:
            return 'none'

    def get_midpoint(self, x1, y1, x2, y2):
        """
        Calculates the midpoint between two points.

        Args:
            x1 (float): x-coordinate of the first point.
            y1 (float): y-coordinate of the first point.
            x2 (float): x-coordinate of the second point.
            y2 (float): y-coordinate of the second point.

        Returns:
            tuple: The midpoint (x, y).
        """
        return (x1 + x2) / 2, (y1 + y2) / 2

    def get_zone_dets_paint_point(self, preds, original_frame):
        """
        Filters detections based on whether they are inside the tracking zone and draws points on out-of-zone detections.

        Args:
            preds (list): List of detections, where each detection is a list [x1, y1, x2, y2, confidence, class_id].
            original_frame (np.ndarray): The original frame.

        Returns:
            tuple: A tuple containing:
                - np.ndarray: An array of detections that are inside the tracking zone.
                - np.ndarray: The original frame with points drawn on out-of-zone detections.
        """
        preds_to_track = []
        for x1, y1, x2, y2, conf, cls_id in preds:
            midx, midy = self.get_midpoint(x1, y1, x2, y2)
            if self.recty1 <= midy <= self.recty2 and self.rectx1 <= midx <= self.rectx2:
                preds_to_track.append([x1, y1, x2, y2, conf, cls_id])
            else:
                # cv2.circle(original_frame, center=(int(midx), int(midy)), radius=1, color=(0, 0, 255), thickness=2)
                drawCircle(self.debug, original_frame, midx, midy, radius=1, color=(0, 0, 255), thickness=2)
                
            
            # cv2.rectangle(original_frame, (int(x1), int(y1)), (int(x2), int(y2)), color=(255, 255, 255), thickness=1)
            drawRectangle(self.debug, original_frame, int(x1), int(y1), int(x2), int(y2), color=(255, 255, 255), thickness=1)
            # cv2.circle(original_frame, center=(int(midx), int(midy)), radius=1, color=(0, 0, 255), thickness=2)
            drawCircle(self.debug, original_frame, midx, midy, radius=1, color=(0, 0, 255), thickness=2)
                
        return np.array(preds_to_track), original_frame

    def get_point_distance(self, p1, p2):
        """
        Calculates the Euclidean distance between two points.

        Args:
            p1 (tuple): The first point (x, y).
            p2 (tuple): The second point (x, y).

        Returns:
            float: The distance between the two points.
        """
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def process_frames(self, original_frame, preds):
        """
        Processes a single frame to perform head counting with timed display.

        Args:
            original_frame (np.ndarray): The original frame.
            preds (list): List of detections.

        Returns:
            int or None: Returns 1 if the 'Esc' key is pressed (for windowed mode), otherwise None.
        """
        self.frame_count += 1
        current_time = time.time() # Get current time for timeout check

        # Filter detections based on tracking zone and draw points on out-of-zone detections
        preds_in_zone, original_frame = self.get_zone_dets_paint_point(preds, original_frame)
        
        # Draw tracking zone rectangle
        # cv2.rectangle(original_frame, (self.rectx1, self.recty1), (self.rectx2, self.recty2), (255, 0, 0), 1)
        drawRectangle(self.debug, original_frame, self.rectx1, self.recty1, self.rectx2, self.recty2, color=(255, 0, 0), thickness=1)

        # Update tracker with detections inside the zone
        tracking_output = self.tracker.update(preds_in_zone, original_frame)

        event_occurred_this_frame = False # Flag to check if any in/out happened

        # Process each tracked object
        for x3, y3, x4, y4, track_id, conf, cls, det_ind in tracking_output:
            # Draw tracked ID
            # cv2.putText(original_frame, str(int(track_id)), (int(x3 + 1), int(y3 + 1)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (55, 255, 0), 2)
            drawText(self.debug, original_frame, str(int(track_id)), int(x3 + 1), int(y3 + 1), color=(55, 255, 0), fontScale=0.5, thickness=2)

            # Calculate current midpoint
            midx, midy = self.get_midpoint(x3, y3, x4, y4)
            current_midpoint = (midx, midy)
            
            # Check if the track ID exists in the previous midpoint dictionary
            if track_id in self.previous_midpoint_dict:
                previous_midpoint = self.previous_midpoint_dict[track_id]
                distance = self.get_point_distance(current_midpoint, previous_midpoint)

                #if_logic = distance < self.min_movement_distance                
                #print(f"If_logic: {if_logic}, Distance: {distance}, Min Movement Distance: {self.min_movement_distance}") # Debugging output
                # Skip if the distance moved is too small 
                if distance < self.min_movement_distance:
                    continue

                min_distance_not_meet = False
                enter_or_exit_found = False # Renamed for clarity

                #print(f"len of: {preds}")

                # Check for intersection with each entrance line
                for entrance_line in self.entrance_lines:
                    intersect = self.intersect(previous_midpoint + current_midpoint,
                                               entrance_line[0] + entrance_line[1])

                    if intersect == 'true':
                        enter_or_exit_found = True
                        dir_movement = self.direction_of_movement(previous_midpoint, current_midpoint,
                                                                  entrance_line[0] + entrance_line[1])
                        #print(f"Direction of movement: {dir_movement}") # Debugging output
                        
                        # Only for debugging
                        start_point = (int(previous_midpoint[0]), int(previous_midpoint[1]))
                        end_point = (int(current_midpoint[0]), int(current_midpoint[1]))
                        
                        if dir_movement == 'entering':
                            self.enter_count += 1 # Keep total count if needed
                            self.display_enter_count += 1 # Increment display count
                            event_occurred_this_frame = True
                            
                            if self.debug:
                                self.debug_lines.append((start_point, end_point, self.color_in))
                                
                        elif dir_movement == 'exiting':
                            self.exit_count += 1 # Keep total count if needed
                            self.display_exit_count += 1 # Increment display count
                            event_occurred_this_frame = True
                            
                            if self.debug:
                                self.debug_lines.append((start_point, end_point, self.color_out))
                        
                        self.previous_midpoint_dict.pop(track_id)        
                        # Break if intersection found for this track_id on any line
                        break
                    elif intersect == "min_distance_not_meet":
                        min_distance_not_meet = True

                # Skip updating midpoint if min distance wasn't met and no intersection was found
                # This logic might need review depending on exact intersect behavior
                if min_distance_not_meet and not enter_or_exit_found:
                    # THIS IS CURRENTLY NOT BEING USED AS THE ONLY MIDPOINT ENTRY BEING TAKEN IS THE FIRST ONE
                    continue
                
            else:
                # Add track id only once at the start, never update until crossing
                self.previous_midpoint_dict[track_id] = current_midpoint

        # --- Timed Display Logic ---
        if event_occurred_this_frame:
            self.last_event_time = current_time # Reset timer on new event
            self.show_display_counts = True     # Ensure display is active
        elif self.show_display_counts:
            # Check if timeout has expired since the last event
            if current_time - self.last_event_time > self.display_timeout:
                self.show_display_counts = False # Turn off display
                self.display_enter_count = 0     # Reset display counters
                self.display_exit_count = 0
                
                # Empty debug lines
                if self.debug:
                    self.debug_lines = []

        self.process_data()
        
        # Draw entrance lines
        for line in self.entrance_lines:
            drawLine(self.debug, original_frame, (line[0][0], line[0][1]), (line[1][0], line[1][1]), color=(255,255,0), thickness=2)

        text = f"In: +{self.display_enter_count} Out: +{self.display_exit_count}" # Use display counts with '+'
        font = cv2.FONT_HERSHEY_COMPLEX_SMALL
        font_scale = 1
        font_thickness = 1
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, font_thickness)

        box_margin = 5  # Margin around the text

        # Calculate coordinates for the right corner
        frame_width = original_frame.shape[1]  # Get the width of the frame
        box_width = text_width + 2 * box_margin
        box_height = text_height + baseline + 2 * box_margin # Include baseline in height
        box_x = frame_width - box_width - 20 # 20 is the original x-offset from right edge
        box_y = 10 # Y position from top edge

        # Create a black rectangle as the background
        drawRectangle(self.debug, original_frame, box_x, box_y, (box_x + box_width), (box_y + box_height), color=(0, 0, 0), thickness=-1)

        # Put the white text on top of the black box. Adjust text position to be inside the box
        text_x = box_x + box_margin
        text_y = box_y + text_height + box_margin # Position text baseline correctly
        drawText(self.debug, original_frame, text, text_x, text_y, color=(255, 255, 255), fontScale=font_scale, thickness=font_thickness)
        
        # if self.debug:        
        #     for start_point, end_point, color in self.debug_lines:
        #         cv2.line(original_frame, start_point, end_point, color, self.debug_line_thickness)

        return original_frame

    def process_data(self):
        if time.time() - self.start_time > self.datasend_interval:
            total_in = self.enter_count - self.inSend
            total_out = self.exit_count - self.outSend

            # if there is data change, send count update
            if not (total_in == 0 and total_out == 0): 
                self.inSend += total_in
                self.outSend += total_out
                end_time = time.time()
                
                self.people_count_data.append({
                    "sn": self.sn,
                    "total_in": total_in,
                    "total_out": total_out,
                    "total": total_in + total_out,
                    "start_time": time_to_string(self.start_time),
                    "end_time": time_to_string(end_time),
                })
                self.start_time = end_time

