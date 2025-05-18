import time
import cv2

def time_to_string(input):
    time_tuple = time.gmtime(input)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time_tuple)

def mat_to_response(frame):
    # Encode the image to JPEG format in memory
    ret, encoded_image = cv2.imencode(".jpg", frame)
    if not ret:
        print("Error: Could not encode image.")
        return

    # Convert the encoded image to bytes
    image_bytes = encoded_image.tobytes()

    # Prepare files for sending
    return ("image.jpg", image_bytes, "image/jpeg")

def does_boxes_overlap_by(box1, box2, by = 0.8):
    # print(f"Box1: {box1},\nBox2: {box2}")
    # formatted_box_1 = [box1['xmin'], box1['ymin'], box1['xmax'], box1['ymax']]
    # formatted_box_2 = [box2['xmin'], box2['ymin'], box2['xmax'], box2['ymax']]

    return does_box_overlap_enough(box1, box2, threshold=by)
    #return calculate_iou(formatted_box_1, formatted_box_2) >= by

def calculate_iou(box1, box2):
    """
    Calculates the Intersection over Union (IoU) of two bounding boxes.

    Args:
        box1: A list or tuple representing the first box in the format [x1, y1, x2, y2].
        box2: A list or tuple representing the second box in the format [x1, y1, x2, y2].

    Returns:
        The IoU value (float) between 0 and 1.
    """
    # Determine the (x, y)-coordinates of the intersection rectangle
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])

    # Compute the area of intersection rectangle
    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)

    # Compute the area of both the prediction and ground-truth rectangles
    box1Area = (box1[2] - box1[0] + 1) * (box1[3] - box1[1] + 1)
    box2Area = (box2[2] - box2[0] + 1) * (box2[3] - box2[1] + 1)

    # Compute the intersection over union by taking the intersection area and dividing it by the sum of prediction + ground-truth areas - the intersection area
    iou = interArea / float(box1Area + box2Area - interArea)

    return iou

def does_box_overlap_enough(box1, box2, threshold):
    """
    Returns True if the overlap between box1 and box2 is at least `threshold`
    of either box's area.

    Args:
        box1, box2: Lists or tuples in [x1, y1, x2, y2] format
        threshold: Minimum fraction of overlap required (default 0.8)

    Returns:
        True if boxes overlap enough, False otherwise
    """
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])

    inter_width = max(0, xB - xA)
    inter_height = max(0, yB - yA)
    inter_area = inter_width * inter_height

    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])

    if box1_area == 0 or box2_area == 0:
        return False  # One of the boxes is invalid

    overlap_ratio_1 = inter_area / box1_area
    overlap_ratio_2 = inter_area / box2_area

    #print(f"Overlap Ratio 1: {overlap_ratio_1}, Overlap Ratio 2: {overlap_ratio_2}")
    return overlap_ratio_1 >= threshold or overlap_ratio_2 >= threshold


# if __name__ == "__main__":
#     # Test the functions
#     box2 = [0, 0, 10, 10]
#     box1 = [9, 9, 10, 10]
#     print(does_box_overlap_enough(box1, box2))  # Should return True
#     print(calculate_iou(box1, box2))  # Should return IoU value