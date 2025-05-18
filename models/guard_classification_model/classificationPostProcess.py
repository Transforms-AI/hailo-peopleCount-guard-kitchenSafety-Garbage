import numpy as np
import json

def postprocess_classification_output(output, labels_file, topk=5):
    """
    Postprocesses the model output to extract top-k predictions, maps them to labels,
    and adjusts class indices based on label length compatibility.

    Args:
        output (list): The raw model output containing quantized data and metadata.
        labels_file (str): Path to the JSON file containing the list of labels.
        topk (int): Number of top predictions to extract.

    Returns:
        list of dict: List of dictionaries containing adjusted_class_id, class_id, labels, and probabilities.
    """
    # Load labels from the JSON file
    with open(labels_file, "r") as f:
        labels = json.load(f)  

    # Extract the first output (assuming only one output is present)
    output_data = output[0]

    # Extract relevant fields
    data = output_data['data']  # Quantized data
    scale = output_data['quantization']['scale'][0]  # Quantization scale
    zero = output_data['quantization']['zero'][0]  # Quantization zero point

    # Dequantize the data
    dequantized_data = (data.astype(np.float32) - zero) * scale

    # Flatten the data (assumes shape [1, 1, 1, N])
    dequantized_data = dequantized_data.flatten()

    # Get the top-k indices and probabilities
    top_k_indices = np.argsort(dequantized_data)[-topk:][::-1]  # Indices of top-k predictions
    top_k_probs = dequantized_data[top_k_indices]  # Probabilities of top-k predictions

    # Determine if class_index should be adjusted
    if len(labels) == len(dequantized_data):
        subtract_one = False
    elif len(labels) == len(dequantized_data) - 1:
        subtract_one = True
    else:
        print(f"Warning: Labels file is not compatible with output results. "
              f"Labels length: {len(labels)}, Output length: {len(dequantized_data)}")
        return []    

    # Process the results and map to labels
    processed_results = []
    for class_index, probability in zip(top_k_indices, top_k_probs):
        if subtract_one:
            # Adjust class_index if needed
            adjusted_class_index = class_index - 1
            if class_index == 0:
                label = "Background"  # Background class exists only when subtract_one is True
            elif 0 <= adjusted_class_index < len(labels):
                label = labels[str(adjusted_class_index)]
            else:
                label = "Unknown"
        else:
            # No adjustment needed for class_index
            adjusted_class_index = class_index
            if 0 <= adjusted_class_index < len(labels):
                label = labels[str(adjusted_class_index)]
            else:
                label = "Unknown"

        processed_results.append({
            "category_id": adjusted_class_index,
            "label": label,
            "score": probability
        })

    return processed_results