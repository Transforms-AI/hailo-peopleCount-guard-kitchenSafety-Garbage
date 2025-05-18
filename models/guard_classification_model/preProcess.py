import cv2
import numpy as np


def preprocess_image_for_regnetx(
    image_path: str,
    height: int = 224,
    width: int = 224
) -> np.ndarray:
    """
    Loads an image from disk, resizes it, normalizes to ImageNet stats,
    and formats it to (1, 3, H, W) float32 tensor for RegNetX inference.

    Args:
        image_path (str): Path to the input image.
        height (int): Target height in pixels (default 224).
        width (int): Target width in pixels (default 224).

    Returns:
        np.ndarray: Preprocessed image array of shape (1, 3, height, width).

    Raises:
        FileNotFoundError: If the image could not be loaded from the path.
    """
    # Load image with OpenCV (BGR)
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image at '{image_path}'")

    # Convert to RGB
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Resize with bilinear interpolation
    image = cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)

    # Convert to float32 and scale to [0, 1]
    image = image.astype(np.float32) / 255.0

    # Normalize using ImageNet mean and std
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    image = (image - mean) / std

    # Change HWC to CHW
    image = np.transpose(image, (2, 0, 1))

    # Add batch dimension
    return np.expand_dims(image, 0)