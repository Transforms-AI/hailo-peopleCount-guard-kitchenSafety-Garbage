import onnxruntime
import numpy as np
import os
import sys
import cv2
def load_and_preprocess_image(image_path, input_shape=(640, 640)):
    """
    Load and preprocess an image to match the required input shape (1, 3, 640, 640)
    """
    # Check if file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Read the image with OpenCV (in BGR format)
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
    
    # Resize to the required dimensions
    img = cv2.resize(img, input_shape)
    
    # Convert BGR to RGB (if your model expects RGB)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Normalize pixel values to [0,1]
    img = img.astype('float32') / 255.0
    
    # Transpose from HWC to CHW format
    img = img.transpose(2, 0, 1)
    
    # Add batch dimension
    img = np.expand_dims(img, axis=0)
    
    return img

def process_and_save_output(original_image_path, outputs, output_image_path="detection_result.jpg", conf_threshold=0.25):
    """
    Process model outputs, draw detections on the original image, and save the result
    """
    # Load original image for visualization
    original_image = cv2.imread(original_image_path)
    if original_image is None:
        raise ValueError(f"Could not read original image: {original_image_path}")
    
    # Get original image dimensions
    original_height, original_width = original_image.shape[:2]
    
    # The first output shape is (1, 48, 8400) which appears to be detection outputs
    # Format is likely [batch, num_classes+box_params, num_anchors]
    detections = outputs[0]
    
    # Process detections (adjust this based on your specific model's output format)
    # Typically for modern detectors: first 4 values are box coordinates, rest are class scores
    boxes = []
    scores = []
    class_ids = []
    
    # Assuming format: [xywh, confidence, class_scores...]
    num_classes = detections.shape[1] - 5  # Subtract box params (4) and confidence (1)
    
    # Transpose to get [num_anchors, num_params]
    detections = detections[0].transpose()  # Shape: [8400, 48]
    
    for detection in detections:
        # Get confidence score
        confidence = detection[4]
        
        if confidence >= conf_threshold:
            # Get class scores
            class_scores = detection[5:]
            class_id = np.argmax(class_scores)
            class_score = class_scores[class_id]
            score = float(confidence * class_score)
            
            if score >= conf_threshold:
                # Get bounding box coordinates (assumed to be in center_x, center_y, width, height format)
                cx, cy, w, h = detection[0:4]
                
                # Convert to corner format (x1, y1, x2, y2)
                x1 = int((cx - w/2) * original_width)
                y1 = int((cy - h/2) * original_height)
                x2 = int((cx + w/2) * original_width)
                y2 = int((cy + h/2) * original_height)
                
                # Make sure coordinates are within image boundaries
                x1 = max(0, min(x1, original_width - 1))
                y1 = max(0, min(y1, original_height - 1))
                x2 = max(0, min(x2, original_width - 1))
                y2 = max(0, min(y2, original_height - 1))
                
                boxes.append([x1, y1, x2, y2])
                scores.append(score)
                class_ids.append(class_id)
    
    # Draw detections on the image
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = box
        score = scores[i]
        class_id = class_ids[i]
        
        # Draw bounding box
        color = (0, 255, 0)  # Green color for the box (BGR format)
        cv2.rectangle(original_image, (x1, y1), (x2, y2), color, 2)
        
        # Create label
        label = f"Class {class_id}: {score:.2f}"
        
        # Draw label background
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
        cv2.rectangle(original_image, (x1, y1 - text_size[1] - 5), (x1 + text_size[0], y1), color, -1)
        
        # Draw label text
        cv2.putText(original_image, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    
    # Save output image
    cv2.imwrite(output_image_path, original_image)
    print(f"Detection result saved to {output_image_path}")
    
    return len(boxes)  # Return number of detections

def main():
    # Make sure the model file exists
    HAILO_ONNX_MODEL = "./models/best.onnx"
    if not os.path.exists(HAILO_ONNX_MODEL):
        print(f"Error: Model file '{HAILO_ONNX_MODEL}' not found")
        return
    
    # Create sample input data
    input_image_path = "./input/ss-kitchen-3.png"
    data = load_and_preprocess_image(input_image_path, input_shape=(640, 640))
    print(type(data))

    # Configure Hailo execution provider
    provider_options = {}  # You can add specific Hailo options here if needed
    ep_list = [('HailoExecutionProvider', provider_options)]
    
    try:
        # Create inference session with Hailo provider
        session = onnxruntime.InferenceSession(HAILO_ONNX_MODEL, providers=ep_list)
        
        # Run inference
        outputs = session.run([output.name for output in session.get_outputs()], 
                             {session.get_inputs()[0].name: data})

        process_and_save_output(original_image_path=input_image_path, outputs = outputs, output_image_path="./output/onnx/ss-kitchen-3.png")
        
        print("Inference successful!")
        print(f"Output shapes: {[output.shape for output in outputs]}")
        
    except Exception as e:
        print(f"Error running inference: {e}")

if __name__ == "__main__":
    main()
