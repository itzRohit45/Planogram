import sys
import argparse
import json
import cv2
import os
import torch
import torchvision.transforms as transforms
import warnings

# Suppress annoying xFormers and TypedStorage warnings from DINOv2
warnings.filterwarnings("ignore", category=UserWarning)
from PIL import Image
import torch.nn.functional as F
from ultralytics import YOLO
import numpy as np

def extract_fingerprint(image_path):
    device = torch.device('cpu')
    
    # Load YOLO to auto-crop the product from background
    try:
        model_path = os.path.join(os.path.dirname(__file__), 'notebooks/test/best_model_yolov8s.pt')
        yolo_model = YOLO(model_path)
        yolo_model.to(device)
    except Exception as e:
        yolo_model = None
        print(f"Warning: YOLO failed to load, falling back to full image: {e}", file=sys.stderr)

    # Load DINOv2
    feature_extractor = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitb14', verbose=False)
    feature_extractor = feature_extractor.to(device)
    feature_extractor.eval()

    # DINOv2 preprocessing
    dino_preprocess = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")

    # YOLO Auto-Cropping
    crop_img = img
    if yolo_model is not None:
        results = yolo_model(img, verbose=False)
        best_area = 0
        best_box = None
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area = (x2 - x1) * (y2 - y1)
                if area > best_area:
                    best_area = area
                    best_box = (int(x1), int(y1), int(x2), int(y2))
        
        if best_box is not None:
            x1, y1, x2, y2 = best_box
            crop_img = img[y1:y2, x1:x2]

    # Process the cropped image with DINOv2
    crop_rgb = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(crop_rgb)
    tensor_img = dino_preprocess(pil_img).unsqueeze(0).to(device)

    with torch.no_grad():
        features = feature_extractor(tensor_img)
        features = F.normalize(features, p=2, dim=1)

    # Compute color histogram on the center 60% to avoid background pixels
    ch, cw = crop_img.shape[:2]
    cy1, cy2 = int(ch * 0.2), int(ch * 0.8)
    cx1, cx2 = int(cw * 0.2), int(cw * 0.8)
    
    if cy2 > cy1 and cx2 > cx1:
        center_crop = crop_img[cy1:cy2, cx1:cx2]
    else:
        center_crop = crop_img
        
    hsv_crop = cv2.cvtColor(center_crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv_crop], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    color_hist = hist.flatten().tolist()

    return features[0].tolist(), color_hist

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True, help='Path to catalog image')
    args = parser.parse_args()

    try:
        fingerprint, color_hist = extract_fingerprint(args.image)
        print(json.dumps({"fingerprint": fingerprint, "color_hist": color_hist}))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
