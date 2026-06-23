import json
import os
import cv2
from ultralytics import YOLO

# 1. Configuration
MODEL_CHECKPOINT_PATH = "/Users/rohit/Downloads/Planogram/ml-service/notebooks/test/best_model_yolov8s.pt"
INPUT_IMAGE_PATH = "/Users/rohit/Downloads/Planogram/ml-service/audit/audit.png" # Switch to 2.jpg or 3.jpg here

# 2. Define highly visible, bright colors (BGR Format for OpenCV)
# This sequence helps you visually distinguish tightly packed, adjacent products easily.
VISUAL_COLORS = [
    (0, 255, 0),     # Neon Green
    (255, 0, 255),   # Magenta Pink
    (0, 255, 255),   # Vibrant Yellow
    (255, 255, 0),   # Bright Cyan Blue
    (0, 165, 255),   # Deep Orange
    (255, 0, 0),     # Pure Blue
]

print("Loading native YOLOv8 Model weights...")
model = YOLO(MODEL_CHECKPOINT_PATH)

print(f"Processing image: {INPUT_IMAGE_PATH} ...")
# Run prediction *without* using the default save=True to prevent text/confidence overlay clutter
results = model.predict(source=INPUT_IMAGE_PATH, conf=0.25, save=False)

# 3. Read the original image natively with OpenCV to paint custom borders
original_img = cv2.imread(INPUT_IMAGE_PATH)

result = results[0]
bboxes = result.boxes.xyxy.cpu().numpy()       # [xmin, ymin, xmax, ymax]
confidence = result.boxes.conf.cpu().numpy()   # Confidence scores
labels = result.boxes.cls.cpu().numpy()        # Class integers

output_boxes = []

# 4. Loop through every box and draw borders onto our canvas
for i in range(len(bboxes)):
    xmin, ymin, xmax, ymax = bboxes[i]
    
    # Store clean tracking dictionary configurations for coordinates.json
    output_boxes.append({
        "id": i,
        "box": [float(xmin), float(ymin), float(xmax), float(ymax)],
        "confidence": float(confidence[i]),
        "label": int(labels[i])
    })
    
    # Convert box corners to integers for pixel rendering
    start_point = (int(xmin), int(ymin))
    end_point = (int(xmax), int(ymax))
    
    # Cycle dynamically through our vibrant color palette
    box_color = VISUAL_COLORS[i % len(VISUAL_COLORS)]
    
    # Draw a clean box border with a crisp line thickness of 2 pixels (NO text/confidence scores drawn)
    cv2.rectangle(original_img, start_point, end_point, box_color, 2)

# 5. Create directory and save dynamically tracking filename layout structures
OUTPUT_DIR = "./output_predict"
os.makedirs(OUTPUT_DIR, exist_ok=True)
output_filename = os.path.basename(INPUT_IMAGE_PATH)
output_image_path = os.path.join(OUTPUT_DIR, output_filename)

# Write custom modified image canvas out to the folder path
cv2.imwrite(output_image_path, original_img)

# Save structural metrics entries array to coordinates.json
with open("coordinates.json", "w") as f:
    json.dump({"boxes": output_boxes}, f, indent=4)

print(f"\n==========================================")
print(f"SUCCESS!")
print(f"Processed {len(output_boxes)} total objects on the shelf.")
print(f"Visual Photo (Borders Only, No Text) saved to: {output_image_path}")
print(f"Coordinates dictionary written to: ./coordinates.json")
print(f"==========================================")