# Shelf Compliance Auditing System - Project Plan

## Overview
This system aims to automate the auditing of retail shelves to ensure product compliance, track fill rates, and detect anomalies such as missing, extra, or misaligned products.

## Phases

### Phase 1: Foundation & ML Baseline
- Setup repository structure (Frontend, Backend, ML Service).
- Migrate and organize existing YOLO-NAS notebooks.
- Run baseline model training (`1_dataset_preparation.ipynb` -> `2_model_training.ipynb`).
- Store trained weights securely and deploy the initial inference script.

### Phase 2: Backend Development (Node.js + Express)
- Define API contracts for uploading baseline and audit images.
- Set up upload directories and static file serving for generated reports.
- Integrate backend with the Python ML Service for product detection.
- Develop compliance logic (calculate fill rate, detect missing/extra items).

### Phase 3: Frontend Development (Angular)
- Set up Angular application architecture and core services.
- Implement dashboard to view compliance metrics.
- Build components for baseline and audit uploads.
- Build image comparison view highlighting discrepancies.

### Phase 4: Reporting & Actionable Insights
- Implement visual report generation (bounding boxes, highlighted issues).
- Generate JSON and HTML reports.
- Add historical report tracking and comparison.

### Phase 5: Future Enhancements
- Wrong Product Detection (requires classification model).
- Batch Processing for multiple shelves/aisles simultaneously.
