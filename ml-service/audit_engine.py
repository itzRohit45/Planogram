import sys
import argparse
import json
import cv2
import numpy as np
import os
import math
import sqlite3
from datetime import datetime
from ultralytics import YOLO

import torch
import torch.nn as nn
import torchvision.transforms as transforms
import warnings

# Suppress annoying xFormers and TypedStorage warnings from DINOv2
warnings.filterwarnings("ignore", category=UserWarning)
from PIL import Image
import torch.nn.functional as F
from scipy.optimize import linear_sum_assignment

# 1. Model Initialization
model_path = os.path.join(os.path.dirname(__file__), 'notebooks/test/best_model_yolov8s.pt')
model = YOLO(model_path)

device = torch.device('cpu')
feature_extractor = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitb14', verbose=False)
feature_extractor = feature_extractor.to(device)
feature_extractor.eval()

dino_preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def load_catalog():
    db_path = os.path.join(os.path.dirname(__file__), '../backend/database.sqlite')
    catalog = []
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT name, fingerprint, color_hist, aspect_ratio, orb_descriptors, ocr_text FROM products")
            for row in c.fetchall():
                name = row[0]
                fp = json.loads(row[1])
                ch = json.loads(row[2]) if row[2] else None
                ar = row[3] if row[3] else 0.0
                orb = json.loads(row[4]) if row[4] else []
                ocr = row[5] if row[5] else ""
                
                catalog.append({
                    'name': name,
                    'fingerprint': torch.tensor(fp, dtype=torch.float32).to(device),
                    'color_hist': np.array(ch, dtype=np.float32) if ch else None,
                    'aspect_ratio': ar,
                    'orb_descriptors': np.array(orb, dtype=np.uint8) if orb else None,
                    'ocr_text': ocr
                })
            conn.close()
        except Exception as e:
            print(f"[DEBUG] Failed to load catalog: {e}", file=sys.stderr)
    return catalog

def match_product(fingerprint, color_hist, crop_bgr, catalog):

    
    ch, cw = crop_bgr.shape[:2]
    aspect_ratio = round(cw / float(ch), 4) if ch > 0 else 0.0
    
    scores = []
    
    for p in catalog:
        dino_score = F.cosine_similarity(fingerprint.unsqueeze(0), p['fingerprint'].unsqueeze(0)).item()
        
        color_score = 0.0
        if color_hist is not None and p.get('color_hist') is not None:
            corr = cv2.compareHist(color_hist, p['color_hist'], cv2.HISTCMP_CORREL)
            color_score = max(0.0, corr)
            
        score = (dino_score * 0.8) + (color_score * 0.2)
        scores.append((score, p))
        
    scores.sort(key=lambda x: x[0], reverse=True)
    
    if len(scores) == 0:
        return "Unknown Product", {}
        
    top1_score, top1_p = scores[0]
    top2_score = scores[1][0] if len(scores) > 1 else 0.0
    
    score_dict = {p['name']: round(s, 4) for s, p in scores}
    
    if top1_score < 0.60:
        return "Unknown Product", score_dict
        
    # Phase 2: Confidence
    margin = top1_score - top2_score
    if margin > 0.08:
        print(f"[DEBUG] DINO_CONFIDENT: {top1_p['name']} (score: {top1_score:.4f})", file=sys.stderr)
        return top1_p['name'], score_dict
        
    # Phase 3: ORB Tie-breaker for close scores
    if margin <= 0.08:
        print(f"[DEBUG] Scores close, running ORB tie-breaker...", file=sys.stderr)
        orb = cv2.ORB_create(nfeatures=500)
        gray_crop = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        kp1, des1 = orb.detectAndCompute(gray_crop, None)
        
        if des1 is not None and len(des1) > 0:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            orb_results = []
            for s, p in scores[:3]:
                des2 = p.get('orb_descriptors')
                if des2 is not None and len(des2) > 0:
                    try:
                        matches = bf.match(des1, des2)
                        orb_results.append((len(matches), p))
                    except Exception:
                        pass
                        
            if orb_results:
                orb_results.sort(key=lambda x: x[0], reverse=True)
                top_orb_matches, top_orb_p = orb_results[0]
                second_orb_matches = orb_results[1][0] if len(orb_results) > 1 else 0
                
                print(f"[DEBUG] ORB Match counts: 1st={top_orb_matches}, 2nd={second_orb_matches}", file=sys.stderr)
                if top_orb_matches > 10 and (top_orb_matches > second_orb_matches * 1.3):
                    print(f"[DEBUG] ORB_VERIFIED: {top_orb_p['name']} (matches: {top_orb_matches})", file=sys.stderr)
                    return top_orb_p['name'], score_dict
                

                
    # Fallback
    print(f"[DEBUG] Tie-breakers failed, falling back to top match: {top1_p['name']}", file=sys.stderr)
    return top1_p['name'], score_dict

def detect_products(image_path, catalog, save_crops=False, crop_dir=None):
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
            cx1, cy1 = max(0, x1), max(0, y1)
            cx2, cy2 = min(w_img, x2), min(h_img, y2)

            if cx2 > cx1 and cy2 > cy1:
                crop_bgr = img[cy1:cy2, cx1:cx2]
                hsv_crop = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
                hist = cv2.calcHist([hsv_crop], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
                cv2.normalize(hist, hist)
                color_hist = hist.flatten()

                crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(crop_rgb)
                tensor_img = dino_preprocess(pil_img)
                crops_tensor.append(tensor_img)

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
                'x1': x1, 'y1': y1,
                'x2': x2, 'y2': y2,
                'w': x2 - x1,
                'h': y2 - y1,
                'cx': int((x1 + x2) / 2),
                'cy': int((y1 + y2) / 2),
                'color_hist': color_hist,
                'crop_img': crop_bgr if cx2 > cx1 and cy2 > cy1 else np.zeros((224, 224, 3), dtype=np.uint8),
                'crop_path': crop_path
            })

    if crops_tensor:
        batch = torch.stack(crops_tensor).to(device)
        with torch.no_grad():
            features = feature_extractor(batch)
            features = F.normalize(features, p=2, dim=1)

        for i in range(len(boxes)):
            fp = features[i]
            ch = boxes[i]['color_hist']
            identity, scores = match_product(fp, ch, boxes[i]['crop_img'], catalog)
            boxes[i]['identity'] = identity
            boxes[i]['scores'] = scores
            
            # Remove non-serializable fields before returning
            if 'color_hist' in boxes[i]:
                del boxes[i]['color_hist']
            if 'crop_img' in boxes[i]:
                del boxes[i]['crop_img']

    return boxes, w_img, h_img

def build_shelves(boxes, height_tolerance=50):
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
    for shelf in shelves:
        shelf.sort(key=lambda x: x['cx'])
    return shelves

def compute_combined_score(b, a, w_baseline, w_audit):
    b_rel_x = b['cx'] / w_baseline
    a_rel_x = a['cx'] / w_audit
    spatial_sim = max(0.0, 1.0 - abs(b_rel_x - a_rel_x) * 3.0)

    visual_sim = 0.0
    if 'fingerprint' in b and 'fingerprint' in a:
        visual_sim = F.cosine_similarity(b['fingerprint'].unsqueeze(0), a['fingerprint'].unsqueeze(0)).item()
        visual_sim = max(0.0, visual_sim)

    color_sim = 0.0
    if b.get('color_hist') is not None and a.get('color_hist') is not None:
        corr = cv2.compareHist(b['color_hist'], a['color_hist'], cv2.HISTCMP_CORREL)
        color_sim = max(0.0, corr)

    final_score = (0.3 * spatial_sim) + (0.5 * visual_sim) + (0.2 * color_sim)
    return final_score, spatial_sim, visual_sim, color_sim

def match_shelf_hungarian(b_shelf, a_shelf, w_baseline, w_audit):
    correct, misaligned, wrong, missing, extra = [], [], [], [], []
    visual_sims, spatial_sims = [], []

    n_baseline = len(b_shelf)
    n_audit = len(a_shelf)

    if n_baseline == 0:
        # All audit products are extra
        for a in a_shelf:
            extra.append({
                'identity': a['identity'],
                'cx': a['cx'], 'cy': a['cy'],
                'a_box': a
            })
        return correct, misaligned, wrong, missing, extra, 0.0, 0.0

    if n_audit == 0:
        # All baseline products are missing
        for b in b_shelf:
            missing.append({
                'identity': b['identity'],
                'cx': b['cx'], 'cy': b['cy'],
                'b_box': b
            })
        return correct, misaligned, wrong, missing, extra, 0.0, 0.0

    score_matrix = np.zeros((n_baseline, n_audit))
    detail_matrix = [[None] * n_audit for _ in range(n_baseline)]

    for i, b in enumerate(b_shelf):
        for j, a in enumerate(a_shelf):
            final, spatial, visual, color = compute_combined_score(b, a, w_baseline, w_audit)
            score_matrix[i][j] = final
            detail_matrix[i][j] = {'final': final, 'spatial': spatial, 'visual': visual, 'color': color}

    cost_matrix = 1.0 - score_matrix
    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    matched_b, matched_a = set(), set()

    for bi, ai in zip(row_indices, col_indices):
        b = b_shelf[bi]
        a = a_shelf[ai]
        details = detail_matrix[bi][ai]

        matched_b.add(bi)
        matched_a.add(ai)

        visual_sims.append(details['visual'])
        spatial_sims.append(details['spatial'])
        
        if b['identity'] == a['identity'] and b['identity'] != "Unknown Product":
             a['match_score'] = details['final']
             if details['spatial'] < 0.60:
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
             if details['final'] >= 0.70:
                 a['match_score'] = details['final']
                 if details['spatial'] < 0.60:
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
             elif details['spatial'] > 0.60 and details['final'] < 0.70:
                 wrong.append({
                    'expected_identity': b['identity'],
                    'actual_identity': a['identity'],
                    'cx': b['cx'], 'cy': b['cy'],
                    'actual_cx': a['cx'], 'actual_cy': a['cy'],
                    'combined_score': round(details['final'], 4),
                    'b_box': b, 'a_box': a
                 })
             else:
                 extra.append({
                    'identity': a['identity'],
                    'a_box': a
                 })
                 matched_b.remove(bi)

    for i in range(n_baseline):
        if i not in matched_b:
            missing.append({
                'identity': b_shelf[i]['identity'],
                'b_box': b_shelf[i]
            })
            
    for j in range(n_audit):
        if j not in matched_a:
            extra.append({
                'identity': a_shelf[j]['identity'],
                'cx': a_shelf[j]['cx'], 'cy': a_shelf[j]['cy'],
                'a_box': a_shelf[j]
            })

    avg_v = sum(visual_sims) / len(visual_sims) if visual_sims else 0.0
    avg_s = sum(spatial_sims) / len(spatial_sims) if spatial_sims else 0.0

    return correct, misaligned, wrong, missing, extra, avg_v, avg_s

def process_audit(baseline_path, audit_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    catalog = load_catalog()

    b_boxes, w_b, h_b = detect_products(baseline_path, catalog, save_crops=False)
    a_boxes, w_a, h_a = detect_products(audit_path, catalog, save_crops=True, crop_dir=os.path.join(output_dir, 'crops'))

    avg_h = sum(b['h'] for b in b_boxes) / len(b_boxes) if b_boxes else 100
    b_shelves = build_shelves(b_boxes, height_tolerance=avg_h * 0.6)
    a_shelves = build_shelves(a_boxes, height_tolerance=avg_h * 0.6)

    total_capacity = len(b_boxes)
    total_found = len(a_boxes)
    fill_rate = (total_found / total_capacity) * 100 if total_capacity > 0 else 0.0
    fill_rate = min(100.0, fill_rate)

    all_correct, all_misaligned, all_wrong, all_missing, all_extra = [], [], [], [], []
    visual_sims, spatial_sims = [], []

    max_shelves = max(len(b_shelves), len(a_shelves))
    shelf_details = []

    for i in range(max_shelves):
        b_s = b_shelves[i] if i < len(b_shelves) else []
        a_s = a_shelves[i] if i < len(a_shelves) else []

        c, m, w, miss, ext, avg_v, avg_s = match_shelf_hungarian(b_s, a_s, w_b, w_a)

        all_correct.extend(c)
        all_misaligned.extend(m)
        all_wrong.extend(w)
        all_missing.extend(miss)
        all_extra.extend(ext)

        if avg_v > 0: visual_sims.append(avg_v)
        if avg_s > 0: spatial_sims.append(avg_s)
        
        products_dict = {}
        for x in b_s:
            if x['identity'] not in products_dict:
                 products_dict[x['identity']] = {'expected': 0, 'found': 0, 'missing': 0, 'extra': 0}
            products_dict[x['identity']]['expected'] += 1
            
        for x in a_s:
            if x['identity'] not in products_dict:
                 products_dict[x['identity']] = {'expected': 0, 'found': 0, 'missing': 0, 'extra': 0}
            products_dict[x['identity']]['found'] += 1

        for k, v in products_dict.items():
            if v['expected'] > v['found']:
                v['missing'] = v['expected'] - v['found']
            elif v['found'] > v['expected']:
                v['extra'] = v['found'] - v['expected']

        shelf_details.append({
            'row': i + 1,
            'correct': len(c),
            'misaligned': len(m),
            'wrong': len(w),
            'missing': len(miss),
            'extra': len(ext),
            'compliance': round((len(c) / len(b_s) * 100) if len(b_s) > 0 else 0, 1),
            'product_details': products_dict
        })

    avg_visual = sum(visual_sims) / len(visual_sims) if visual_sims else 0.0
    avg_spatial = sum(spatial_sims) / len(spatial_sims) if spatial_sims else 0.0

    compliance_score = 0.0
    if total_capacity > 0:
        compliance_score = (len(all_correct) / total_capacity) * 100

    # Clean up non-serializable data from boxes before returning
    def clean_box(b_dict):
        if 'color_hist' in b_dict: del b_dict['color_hist']
        if 'fingerprint' in b_dict: del b_dict['fingerprint']
        
    for category in [all_correct, all_misaligned, all_missing, all_wrong, all_extra]:
        for p in category:
            if 'b_box' in p: clean_box(p['b_box'])
            if 'a_box' in p: clean_box(p['a_box'])

    report = {
        "audit_timestamp": datetime.now().isoformat(),
        "baseline_image": os.path.basename(baseline_path),
        "audit_image": os.path.basename(audit_path),
        "compliance_score": round(compliance_score, 1),
        "fill_rate": round(fill_rate, 1),
        "average_visual_similarity": round(avg_visual, 4),
        "average_spatial_similarity": round(avg_spatial, 4),
        "image_dimensions": {"width": w_a, "height": h_a},
        "row_wise_compliance": shelf_details,
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

    # Generate Visualization
    vis_img = cv2.imread(audit_path)
    for box in all_correct:
        x1, y1, x2, y2 = box['a_box']['x1'], box['a_box']['y1'], box['a_box']['x2'], box['a_box']['y2']
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 255, 0), 4)
    for box in all_misaligned:
        x1, y1, x2, y2 = box['a_box']['x1'], box['a_box']['y1'], box['a_box']['x2'], box['a_box']['y2']
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 215, 255), 4)
    for box in all_wrong:
        x1, y1, x2, y2 = box['a_box']['x1'], box['a_box']['y1'], box['a_box']['x2'], box['a_box']['y2']
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 0, 255), 4)
    for box in all_extra:
        x1, y1, x2, y2 = box['a_box']['x1'], box['a_box']['y1'], box['a_box']['x2'], box['a_box']['y2']
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (255, 0, 0), 4)

    for box in all_missing:
        x1, y1, x2, y2 = box['b_box']['x1'], box['b_box']['y1'], box['b_box']['x2'], box['b_box']['y2']
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 0, 0), -1)
        cv2.putText(vis_img, "MISSING", (x1+5, y1+30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    vis_path = os.path.join(output_dir, 'visual_report.jpg')
    cv2.imwrite(vis_path, vis_img)

    report_path = os.path.join(output_dir, 'report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    return report, vis_path

def run_baseline(image_path):
    try:
        catalog = load_catalog()
        boxes, w, h = detect_products(image_path, catalog)
        capacity = len(boxes)
        print(json.dumps({"shelf_capacity": capacity}))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

def run_audit(baseline_path, audit_path, baseline_capacity):
    try:
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        reports_dir = os.path.join(os.path.dirname(__file__), '../reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        output_dir = os.path.join(reports_dir, timestamp)
        report, vis_path = process_audit(baseline_path, audit_path, output_dir)
        
        # Override total_capacity with the one from the database if provided
        if baseline_capacity is not None and baseline_capacity > 0:
            total_found = report['counts']['correct'] + report['counts']['misaligned'] + report['counts']['wrong'] + report['counts']['extra']
            report['fill_rate'] = min(100.0, (total_found / baseline_capacity) * 100)
            report['compliance_score'] = (report['counts']['correct'] / baseline_capacity) * 100
            
        print(json.dumps({
            "compliance_score": round(report['compliance_score'], 1),
            "fill_rate": round(report['fill_rate'], 1),
            "report_path": f"{timestamp}/report.json",
            "visual_report_path": f"{timestamp}/visual_report.jpg",
            "comparison_report": report
        }))
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Shelf Compliance Audit Engine v3 (DINOv2 + Catalog)")
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
