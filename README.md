# Planogram - AI-Powered Shelf Execution Analytics

Planogram is an intelligent, AI-powered computer vision platform designed to automate retail shelf compliance and auditing. By combining state-of-the-art vision models with a highly responsive, mobile-first dashboard, Planogram compares store shelves in real-time against reference baselines to instantly identify missing, extra, or incorrectly placed products.

## Key Features

- **Advanced Visual Fingerprinting**: Utilizes Meta's DINOv2 self-supervised vision transformer to extract 384-dimensional semantic embeddings from product crops.
- **HSV Color Histogram Analysis**: Adds color-based heuristics to ensure high confidence matching, distinguishing between products with similar shapes but different packaging.
- **Intelligent Object Detection**: Powered by YOLOv8s for real-time bounding box detection of products on shelves.
- **Hungarian Matching Algorithm**: Uses linear sum assignment to perfectly pair audit products to baseline products based on combined visual, spatial, and color similarities.
- **Mobile-First UI with Camera Integration**: Features a stunning, glassmorphic UI built with Angular. Take photos directly from your mobile device using native HTML5 camera integration.
- **Real-time Compliance Dashboards**: Instantly view metrics like Total Baselines, Avg Compliance, and Row-Wise breakdown stats.

## Technologies Used

* **Frontend**: Angular 18, TypeScript, Tailwind-inspired custom SCSS, Lucide Icons, Glassmorphism UI
* **Backend**: Node.js, Express.js, TypeScript, SQLite
* **Machine Learning**: Python, PyTorch, YOLOv8s (Ultralytics), DINOv2 (Meta), OpenCV, SciPy
* **Architecture**: Client-Server with isolated ML microservice layer

## Project Structure

```
Planogram/
├── frontend/          # Angular UI application
├── backend/           # Node.js Express server & SQLite DB
├── ml-service/        # Python computer vision scripts (YOLO, DINOv2)
├── uploads/           # Uploaded baseline and audit images
└── reports/           # Generated visual reports and crops
```

## Setup & Installation

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Angular CLI (`npm install -g @angular/cli`)

### 1. Setup the Python ML Environment
```bash
cd ml-service
python3 -m venv planogram_env
source planogram_env/bin/activate
pip install torch torchvision ultralytics opencv-python scipy numpy
```
*(Note: YOLOv8s weights (`best_model_yolov8s.pt`) must be present in the `ml-service/notebooks/test/` directory)*

### 2. Start the Backend Server
```bash
cd backend
npm install
npm start
```
*(The backend runs on `http://localhost:3000`)*

### 3. Start the Frontend Application
```bash
cd frontend
npm install
npm start
```
*(The frontend runs on `http://localhost:4200`)*

## Mobile Testing
To test the app on a mobile device and use the native camera:
1. Ensure your phone and laptop are on the same Wi-Fi network.
2. Find your laptop's local IP address (e.g., `192.168.0.x`).
3. The frontend is configured to run with `--host 0.0.0.0`, so simply navigate to `http://<YOUR_LOCAL_IP>:4200` on your mobile browser.

## How It Works
1. **Upload Baseline**: Capture or upload an image of a perfectly organized shelf. The system extracts crops, visual embeddings, and logs the baseline.
2. **Run Audit**: Capture an image of a real store shelf.
3. **Analytics**: The ML engine compares the two images row-by-row, scoring bounding boxes using Spatial IoU, DINOv2 Visual Similarity, and Color Match to provide a precise Compliance Score.

---
*Built for the future of retail execution.*
