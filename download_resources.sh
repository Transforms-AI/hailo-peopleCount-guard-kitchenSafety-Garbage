#!/bin/bash
# download_resources.sh
set -e

MODELS_DIR="models"
VIDEOS_DIR="videos"

# Model files and their Google Drive IDs
declare -A MODEL_FILES=(
    ["$MODELS_DIR/best_person_model/best_person_model.hef"]="1raBgfsNcvIiHFaUCrQCLEaEJ7BzdpKEn"
    ["$MODELS_DIR/garbage_detection_model/garbage_detection_model.hef"]="1qESwifvEWmB-apw38TZ-QbSKkP6bBbNf"
    ["$MODELS_DIR/guard_classification_model/guard_classification_model.hef"]="1_evd0XNRnVmaNnNDe-iBOxXAwn0OIyTa"
    ["$MODELS_DIR/guard_detection_model/guard_detection_model.hef"]="1bTpwsmObIDe4apdanvIJri2ZFgeFs2LQ"
    ["$MODELS_DIR/safety_detection_model/safety_detection_model.hef"]="13VA4VwyxK8AZ3SD7_WqGkqw5fvLjzZir"
)

declare -A VIDEO_FILES=(
    ["$VIDEOS_DIR/people-count-test.mp4"]="1BBRVaGU7kY8a_OA60Xg_lj-JDdvLeC_n"
    ["$VIDEOS_DIR/guard_demo.mp4"]="1wDAboybnEMJHMO8O5z6JOCivTmfTLZS6"
    ["$VIDEOS_DIR/kitchen-test-final.mp4"]="1LRbN2BUi-MKlmaRaymw3bY_Mwn8iN2sv"
    ["$VIDEOS_DIR/garbage.mp4"]="1PnGnI5TE7qeLVBHmpYEPGnx70cbZ3e97"
)

# Ensure directories exist
for d in \
    "$MODELS_DIR/best_person_model" \
    "$MODELS_DIR/garbage_detection_model" \
    "$MODELS_DIR/guard_classification_model" \
    "$MODELS_DIR/guard_detection_model" \
    "$MODELS_DIR/safety_detection_model" \
    "$VIDEOS_DIR"
do
    mkdir -p "$d"
done

# Use python -m gdown for maximum compatibility
GDOWN="python3 -m gdown"

# Download models
echo "Checking and downloading model files..."
for file in "${!MODEL_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Downloading $file ..."
        $GDOWN "https://drive.google.com/uc?id=${MODEL_FILES[$file]}" -O "$file"
    else
        echo "$file already exists. Skipping."
    fi
done

# Download videos
echo "Checking and downloading video files..."
for file in "${!VIDEO_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Downloading $file ..."
        $GDOWN "https://drive.google.com/uc?id=${VIDEO_FILES[$file]}" -O "$file"
    else
        echo "$file already exists. Skipping."
    fi
done

echo "All resources checked/downloaded."
