import sys
import argparse
import json
import cv2
import numpy as np
import os
import math
from datetime import datetime
from ultralytics import YOLO

import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image
import torch.nn.functional as F
from scipy.optimize import linear_sum_assignment

# 1. Model Initialization

# YOLO for object detection
model_path = os.path.join(os.path.dirname(__file__), 'notebooks/test/best_model_yolov8s.pt')
model = YOLO(model_path)

# DINOv2 for Visual Fingerprinting (replaces ResNet18)
# dinov2_vits14: 22M params, produces 384-d embeddings
# Self-supervised — trained to find fine-grained visual differences
# Note: Using CPU because PyTorch 2.1.x MPS lacks some DINOv2 ops (upsample_bicubic2d)
device = torch.device('cpu')
feature_extractor = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14', verbose=False)
feature_extractor = feature_extractor.to(device)
feature_extractor.eval()

# DINOv2 preprocessing (different from ResNet — uses 14×14 patch size, expects 224×224)
dino_preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


# 2. Product Detection with Crop Extraction & Feature Extraction

def detect_products(image_path, save_crops=False, crop_dir=None):
    """
    Detect products using YOLO, then for each detection:
    - Crop the product from the original image
    - Compute an HSV color histogram (8×8×8 bins)
    - Extract a 384-d DINOv2 embedding
    - Optionally save the crop image to disk
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to load image: {image_path}")

    h_img, w_img = img.shape[:2]
    results = model(img, verbose=False)
    boxes = []
    crops_tensor = []

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cls_id = int(box.cls[0].item())
            cls_name = model.names[cls_id]

            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

            # Clamp to image bounds
            cx1, cy1 = max(0, x1), max(0, y1)
            cx2, cy2 = min(w_img, x2), min(h_img, y2)

            # Compute color histogram and DINOv2 tensor
            if cx2 > cx1 and cy2 > cy1:
                crop_bgr = img[cy1:cy2, cx1:cx2]

                # HSV Color Histogram (8×8×8 bins)
                hsv_crop = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
                hist = cv2.calcHist([hsv_crop], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
                cv2.normalize(hist, hist)
                color_hist = hist.flatten()

                # DINOv2 tensor preparation
                crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(crop_rgb)
                tensor_img = dino_preprocess(pil_img)
                crops_tensor.append(tensor_img)

                # Save crop if requested
                crop_path = None
                if save_crops and crop_dir:
                    os.makedirs(crop_dir, exist_ok=True)
                    crop_filename = f"crop_{len(boxes):03d}.png"
                    crop_path = os.path.join(crop_dir, crop_filename)
                    cv2.imwrite(crop_path, crop_bgr)
            else:
                crops_tensor.append(torch.zeros(3, 224, 224))
                color_hist = np.zeros(8 * 8 * 8, dtype=np.float32)
                crop_path = None

            boxes.append({
                'identity': cls_name,
                'x1': x1, 'y1': y1,
                'x2': x2, 'y2': y2,
                'w': x2 - x1,
                'h': y2 - y1,
                'cx': int((x1 + x2) / 2),
                'cy': int((y1 + y2) / 2),
                'color_hist': color_hist,  # numpy array
                'crop_path': crop_path
            })

    # Batch DINOv2 inference
    if crops_tensor:
        batch = torch.stack(crops_tensor).to(device)
        with torch.no_grad():
            features = feature_extractor(batch)
            features = F.normalize(features, p=2, dim=1)

        for i in range(len(boxes)):
            boxes[i]['fingerprint'] = features[i]

    return img, boxes


# 3. Shelf Row Grouping

def group_into_shelves(boxes, height_tolerance):
    """Group bounding boxes into shelf rows using y-center clustering."""
    if not boxes:
        return []

    sorted_boxes = sorted(boxes, key=lambda x: x['cy'])
    shelves = []
    current_shelf = [sorted_boxes[0]]
    current_cy = sorted_boxes[0]['cy']

    for box in sorted_boxes[1:]:
        if abs(box['cy'] - current_cy) < height_tolerance:
            current_shelf.append(box)
            current_cy = sum(b['cy'] for b in current_shelf) / len(current_shelf)
        else:
            shelves.append(current_shelf)
            current_shelf = [box]
            current_cy = box['cy']
    shelves.append(current_shelf)

    # Sort each shelf left-to-right
    for shelf in shelves:
        shelf.sort(key=lambda x: x['cx'])

    return shelves


# 4. Hungarian Matching with Combined Scoring

def compute_combined_score(b, a, w_baseline, w_audit):
    """
    Compute a combined similarity score between a baseline box and an audit box.
    
    final_score = 0.3 × spatial + 0.5 × visual + 0.2 × color
    
    - spatial: Based on relative x-position within the image width
    - visual: Cosine similarity of DINOv2 384-d embeddings
    - color: HSV histogram correlation
    """
    # Spatial similarity (relative x-position within image)
    b_rel_x = b['cx'] / w_baseline
    a_rel_x = a['cx'] / w_audit
    spatial_sim = max(0.0, 1.0 - abs(b_rel_x - a_rel_x) * 3.0)  # Scale: 33% shift → 0 similarity

    # Visual similarity (DINOv2 cosine similarity)
    visual_sim = 0.0
    if 'fingerprint' in b and 'fingerprint' in a:
        visual_sim = F.cosine_similarity(
            b['fingerprint'].unsqueeze(0),
            a['fingerprint'].unsqueeze(0)
        ).item()
        visual_sim = max(0.0, visual_sim)

    # Color similarity (HSV histogram correlation)
    color_sim = 0.0
    if 'color_hist' in b and 'color_hist' in a:
        h1 = np.array(b['color_hist'], dtype=np.float32)
        h2 = np.array(a['color_hist'], dtype=np.float32)
        color_sim = cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)
        color_sim = max(0.0, color_sim)

    # Weighted combination
    final_score = 0.3 * spatial_sim + 0.5 * visual_sim + 0.2 * color_sim

    return final_score, spatial_sim, visual_sim, color_sim


def match_shelf_hungarian(b_shelf, a_shelf, w_baseline, w_audit):
    """
    Match products between a baseline shelf row and an audit shelf row
    using the Hungarian algorithm with combined scoring.
    
    Returns:
        correct, misaligned, wrong, missing, extra — lists of product dicts
        avg_visual_sim, avg_spatial_sim — averages for this row
    """
    correct = []
    misaligned = []
    wrong = []
    missing = []
    extra = []
    visual_sims = []
    spatial_sims = []

    n_baseline = len(b_shelf)
    n_audit = len(a_shelf)

    if n_baseline == 0:
        # All audit products are extra
        for a in a_shelf:
            extra.append(a)
        return correct, misaligned, wrong, missing, extra, 0.0, 0.0

    if n_audit == 0:
        # All baseline products are missing
        for b in b_shelf:
            missing.append(b)
        return correct, misaligned, wrong, missing, extra, 0.0, 0.0

    # Build cost matrix (N_baseline × N_audit)
    score_matrix = np.zeros((n_baseline, n_audit))
    detail_matrix = [[None] * n_audit for _ in range(n_baseline)]

    for i, b in enumerate(b_shelf):
        for j, a in enumerate(a_shelf):
            final, spatial, visual, color = compute_combined_score(b, a, w_baseline, w_audit)
            score_matrix[i][j] = final
            detail_matrix[i][j] = {
                'final': final,
                'spatial': spatial,
                'visual': visual,
                'color': color
            }

    # Hungarian assignment (minimize cost, so use 1 - score)
    cost_matrix = 1.0 - score_matrix
    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    matched_b = set()
    matched_a = set()

    for bi, ai in zip(row_indices, col_indices):
        b = b_shelf[bi]
        a = a_shelf[ai]
        details = detail_matrix[bi][ai]

        matched_b.add(bi)
        matched_a.add(ai)

        visual_sims.append(details['visual'])
        spatial_sims.append(details['spatial'])

        if details['final'] >= 0.70:
            # Check spatial shift for misalignment
            b_rel_x = b['cx'] / w_baseline
            a_rel_x = a['cx'] / w_audit
            if abs(b_rel_x - a_rel_x) > 0.15:
                misaligned.append({
                    'identity': b['identity'],
                    'expected_cx': b['cx'], 'expected_cy': b['cy'],
                    'actual_cx': a['cx'], 'actual_cy': a['cy'],
                    'combined_score': round(details['final'], 4),
                    'b_box': b, 'a_box': a
                })
            else:
                correct.append({
                    'identity': b['identity'],
                    'combined_score': round(details['final'], 4),
                    'b_box': b, 'a_box': a
                })
        else:
            wrong.append({
                'expected_identity': b['identity'],
                'actual_identity': 'Visually Different',
                'cx': b['cx'], 'cy': b['cy'],
                'actual_cx': a['cx'], 'actual_cy': a['cy'],
                'combined_score': round(details['final'], 4),
                'visual_similarity': round(details['visual'], 4),
                'color_similarity': round(details['color'], 4),
                'b_box': b, 'a_box': a
            })

    # Unmatched baseline → missing
    for i in range(n_baseline):
        if i not in matched_b:
            missing.append(b_shelf[i])

    # Unmatched audit → extra
    for j in range(n_audit):
        if j not in matched_a:
            extra.append(a_shelf[j])

    avg_visual = sum(visual_sims) / len(visual_sims) if visual_sims else 0.0
    avg_spatial = sum(spatial_sims) / len(spatial_sims) if spatial_sims else 0.0

    return correct, misaligned, wrong, missing, extra, avg_visual, avg_spatial


# 5. Baseline Mode

def run_baseline(image_path):
    try:
        img, boxes = detect_products(image_path)
        # Clean up non-serializable data
        for b in boxes:
            if 'fingerprint' in b: del b['fingerprint']
            if 'color_hist' in b: del b['color_hist']
        capacity = len(boxes)
        print(json.dumps({"shelf_capacity": capacity}))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


# 6. Audit Mode — Full Pipeline

def run_audit(baseline_path, audit_path, baseline_capacity):
    try:
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        reports_dir = os.path.join(os.path.dirname(__file__), '../reports')
        os.makedirs(reports_dir, exist_ok=True)

        # Crop directories
        b_crop_dir = os.path.join(reports_dir, f"crops/baseline_{timestamp}")
        a_crop_dir = os.path.join(reports_dir, f"crops/audit_{timestamp}")

        # Detect products with crop saving
        b_img, b_boxes = detect_products(baseline_path, save_crops=True, crop_dir=b_crop_dir)
        a_img, a_boxes = detect_products(audit_path, save_crops=True, crop_dir=a_crop_dir)

        h1, w1 = b_img.shape[:2]
        h2, w2 = a_img.shape[:2]

        # Group into shelf rows
        avg_h = sum(b['h'] for b in b_boxes) / len(b_boxes) if b_boxes else 100
        b_shelves = group_into_shelves(b_boxes, avg_h * 0.6)
        a_shelves = group_into_shelves(a_boxes, avg_h * 0.6)

        # Results accumulators
        all_correct = []
        all_misaligned = []
        all_wrong = []
        all_missing = []
        all_extra = []
        row_wise_compliance = []
        all_visual_sims = []
        all_spatial_sims = []

        # Match shelf rows (pair by index)
        max_shelves = max(len(b_shelves), len(a_shelves))
        for row_idx in range(max_shelves):
            if row_idx >= len(b_shelves):
                # Entire audit row is extra
                for a in a_shelves[row_idx]:
                    all_extra.append(a)
                row_wise_compliance.append({
                    'row': row_idx + 1,
                    'correct': 0, 'wrong': 0, 'misaligned': 0,
                    'missing': 0, 'extra': len(a_shelves[row_idx]),
                    'compliance': 0.0
                })
                continue

            if row_idx >= len(a_shelves):
                # Entire baseline row is missing
                for b in b_shelves[row_idx]:
                    all_missing.append(b)
                row_wise_compliance.append({
                    'row': row_idx + 1,
                    'correct': 0, 'wrong': 0, 'misaligned': 0,
                    'missing': len(b_shelves[row_idx]), 'extra': 0,
                    'compliance': 0.0
                })
                continue

            # Hungarian matching for this row
            correct, misaligned, wrong, missing, extra, avg_vis, avg_spa = \
                match_shelf_hungarian(b_shelves[row_idx], a_shelves[row_idx], w1, w2)

            all_correct.extend(correct)
            all_misaligned.extend(misaligned)
            all_wrong.extend(wrong)
            all_missing.extend(missing)
            all_extra.extend(extra)

            if avg_vis > 0: all_visual_sims.append(avg_vis)
            if avg_spa > 0: all_spatial_sims.append(avg_spa)

            row_total = len(correct) + len(misaligned) + len(wrong) + len(missing)
            row_compliance = (len(correct) / row_total * 100.0) if row_total > 0 else 0.0

            row_wise_compliance.append({
                'row': row_idx + 1,
                'correct': len(correct),
                'wrong': len(wrong),
                'misaligned': len(misaligned),
                'missing': len(missing),
                'extra': len(extra),
                'compliance': round(row_compliance, 1)
            })

        # Global metrics
        capacity = max(int(baseline_capacity), len(b_boxes), 1)
        correct_count = len(all_correct)
        compliance_score = (correct_count / capacity) * 100.0
        fill_rate = min((len(a_boxes) / capacity) * 100.0, 100.0)
        avg_visual_similarity = sum(all_visual_sims) / len(all_visual_sims) if all_visual_sims else 0.0
        avg_spatial_similarity = sum(all_spatial_sims) / len(all_spatial_sims) if all_spatial_sims else 0.0

        # Create Composite Visualization
        max_h = max(h1, h2)
        composite = np.zeros((max_h, w1 + w2, 3), dtype=np.uint8)
        composite[:h1, :w1, :] = b_img
        composite[:h2, w1:w1 + w2, :] = a_img

        # Colors (BGR)
        GREEN = (0, 255, 0)       # Correct
        ORANGE = (0, 165, 255)    # Misaligned
        RED = (0, 0, 255)         # Missing
        BLUE = (255, 0, 0)        # Extra
        PURPLE = (255, 0, 255)    # Wrong Product

        thickness = 2

        # Draw on Baseline (Left side)
        for c in all_correct:
            b = c['b_box']
            cv2.rectangle(composite, (b['x1'], b['y1']), (b['x2'], b['y2']), GREEN, thickness)
        for m in all_misaligned:
            b = m['b_box']
            cv2.rectangle(composite, (b['x1'], b['y1']), (b['x2'], b['y2']), ORANGE, thickness)
        for w in all_wrong:
            b = w['b_box']
            cv2.rectangle(composite, (b['x1'], b['y1']), (b['x2'], b['y2']), PURPLE, thickness)
        for b in all_missing:
            cv2.rectangle(composite, (b['x1'], b['y1']), (b['x2'], b['y2']), RED, thickness)

        # Draw on Audit (Right side — offset by w1)
        for c in all_correct:
            a = c['a_box']
            cv2.rectangle(composite, (a['x1'] + w1, a['y1']), (a['x2'] + w1, a['y2']), GREEN, thickness)
        for m in all_misaligned:
            a = m['a_box']
            cv2.rectangle(composite, (a['x1'] + w1, a['y1']), (a['x2'] + w1, a['y2']), ORANGE, thickness)
        for w in all_wrong:
            a = w['a_box']
            cv2.rectangle(composite, (a['x1'] + w1, a['y1']), (a['x2'] + w1, a['y2']), PURPLE, thickness)
        for e in all_extra:
            cv2.rectangle(composite, (e['x1'] + w1, e['y1']), (e['x2'] + w1, e['y2']), BLUE, thickness)

        # Save visual report
        visual_filename = f"comparison_{timestamp}.png"
        visual_path = os.path.join(reports_dir, visual_filename)
        cv2.imwrite(visual_path, composite, [cv2.IMWRITE_PNG_COMPRESSION, 1])

        # Clean up non-serializable data before JSON
        def clean_box(box):
            """Remove tensor and numpy fields from a box dict."""
            for key in ['fingerprint', 'color_hist']:
                if key in box:
                    del box[key]

        for category in [all_correct, all_misaligned, all_missing, all_wrong, all_extra]:
            for p in category:
                clean_box(p)
                if 'b_box' in p: clean_box(p['b_box'])
                if 'a_box' in p: clean_box(p['a_box'])

        # Build JSON Report
        report_data = {
            "audit_timestamp": timestamp,
            "baseline_image": os.path.basename(baseline_path),
            "audit_image": os.path.basename(audit_path),
            "compliance_score": round(compliance_score, 1),
            "fill_rate": round(fill_rate, 1),
            "average_visual_similarity": round(avg_visual_similarity, 4),
            "average_spatial_similarity": round(avg_spatial_similarity, 4),
            "image_dimensions": {"width": w2, "height": h2},
            "row_wise_compliance": row_wise_compliance,
            "counts": {
                "correct": len(all_correct),
                "misaligned": len(all_misaligned),
                "missing": len(all_missing),
                "wrong": len(all_wrong),
                "extra": len(all_extra)
            },
            "boxes": {
                "correct": all_correct,
                "misaligned": all_misaligned,
                "missing": all_missing,
                "wrong": all_wrong,
                "extra": all_extra
            }
        }

        # Save JSON report
        json_filename = f"report_{timestamp}.json"
        json_path = os.path.join(reports_dir, json_filename)
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=4)

        # Output for Node.js backend
        print(json.dumps({
            "compliance_score": round(compliance_score, 1),
            "fill_rate": round(fill_rate, 1),
            "report_path": json_filename,
            "visual_report_path": visual_filename,
            "comparison_report": report_data
        }))

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


# 7. CLI Entry Point

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shelf Compliance Audit Engine v2 (DINOv2 + Hungarian)")
    parser.add_argument('--mode', choices=['baseline', 'audit'], required=True)
    parser.add_argument('--image', type=str, help="Path to baseline image (for baseline mode)")
    parser.add_argument('--baseline', type=str, help="Path to baseline image (for audit mode)")
    parser.add_argument('--audit', type=str, help="Path to audit image (for audit mode)")
    parser.add_argument('--capacity', type=int, help="Shelf capacity (for audit mode)")

    args = parser.parse_args()

    if args.mode == 'baseline':
        if not args.image:
            print(json.dumps({"error": "--image is required for baseline mode"}), file=sys.stderr)
            sys.exit(1)
        run_baseline(args.image)

    elif args.mode == 'audit':
        if not args.baseline or not args.audit or args.capacity is None:
            print(json.dumps({"error": "--baseline, --audit, and --capacity are required for audit mode"}), file=sys.stderr)
            sys.exit(1)
        run_audit(args.baseline, args.audit, args.capacity)
