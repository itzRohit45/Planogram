# Planogram - AI-Powered Shelf Execution Analytics

Planogram is an intelligent, AI-powered computer vision platform designed to automate retail shelf compliance and auditing. By combining state-of-the-art vision models with a highly responsive dashboard, Planogram compares store shelves in real-time against reference baselines to instantly identify missing, extra, or incorrectly placed products.

<div align="center">
  <img src="docs/images/dashboard.png" alt="Planogram Dashboard" width="800"/>
</div>

## Key Features

- **Advanced Visual Fingerprinting**: Utilizes Meta's **DINOv2** self-supervised vision transformer to extract 384-dimensional semantic embeddings from product crops.
- **Intelligent Object Detection**: Powered by **YOLOv8s** for real-time bounding box detection of products on shelves.
- **Three-Phase Matching Algorithm**: Uses a sophisticated heuristic engine that combines:
  1. **Visual Similarity (DINOv2 + ORB)**: Matches high-level semantic embeddings and low-level keypoint features.
  2. **Color Similarity (HSV Histograms)**: Matches color profiles to disambiguate visually similar products.
  3. **Spatial Y-Coordinate Clustering**: Groups products into row-levels and performs localized bipartite matching (Hungarian Algorithm) strictly within shelves.
- **Responsive Modern UI**: Features a stunning, glassmorphic UI built with Angular 18.
- **Real-time Compliance Dashboards**: Instantly view metrics like Total Baselines, Avg Compliance, and Row-Wise breakdown stats.

---

## 🏗 System Architecture

Planogram is designed using a modern microservice-style architecture. This allows the compute-heavy Python machine learning tasks to be decoupled from the real-time Node.js backend.

```mermaid
graph TD
    %% Define Styles
    classDef frontend fill:#0ea5e9,stroke:#0284c7,stroke-width:2px,color:#fff,font-weight:bold;
    classDef backend fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff,font-weight:bold;
    classDef ml fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff,font-weight:bold;
    classDef db fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff,font-weight:bold;
    
    %% Nodes
    subgraph "Client Tier"
        A[Angular 18 Frontend]:::frontend
    end

    subgraph "API Tier"
        B[Node.js / Express Backend]:::backend
        DB[(SQLite Database)]:::db
        Files[Local File System]:::db
    end

    subgraph "AI / Vision Tier"
        C[Python ML Engine]:::ml
        Dino[DINOv2 Embeddings]:::ml
        Yolo[YOLOv8s Object Detection]:::ml
        ThreePhase[Three-Phase Matcher]:::ml
    end

    %% Relationships
    A -->|Multipart Upload| B
    B -->|Saves Metadata| DB
    B -->|Saves Images| Files
    B -->|Spawns Child Process| C
    
    C -->|Detects bounding boxes| Yolo
    C -->|Extracts 384d features| Dino
    C -->|Pairs objects via Visual/Color/Spatial| ThreePhase
    
    C -->|Returns JSON Report| B
    B -->|Sends Report| A
```

---

## 🔍 How It Works: The Audit Workflow

<div align="center">
  <img src="docs/images/report.png" alt="Compliance Report" width="800"/>
</div>

### Row-Wise Execution Detail

<div align="center">
  <img src="docs/images/row_wise.png" alt="Row-wise Breakdown" width="800"/>
</div>

When an auditor takes a picture of a store shelf, the image is sent through a rigorous ML pipeline to generate the interactive bounding boxes and row-by-row execution details you see in the UI.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as Angular UI
    participant Backend as Node.js Express
    participant DB as SQLite
    participant Python as ML Engine (Python)

    User->>Frontend: Selects Baseline and uploads photo
    Frontend->>Backend: POST /api/audits (Multipart Form)
    Backend->>Filesystem: Saves raw Audit Image
    Backend->>DB: Fetches Baseline metadata
    Backend->>Python: Spawns child process (audit_engine.py)
    
    activate Python
    Note over Python: 1. YOLOv8s Detection
    Python->>Python: Detect bounding boxes
    
    Note over Python: 2. DINOv2 Extraction
    Python->>Python: Extract 384d embedding per crop
    
    Note over Python: 3. Three-Phase Matching
    Python->>Python: Visual, Color & Spatial Clustering matching
    Python->>Filesystem: Generate visual_report.jpg
    Python-->>Backend: Returns JSON Report (stdout)
    deactivate Python
    
    Backend->>DB: Saves Audit Record
    Backend-->>Frontend: HTTP 200 (AuditResponse JSON)
    Frontend->>User: Renders interactive glowing bounding boxes
```

---

## 🛠 Technologies Used

* **Frontend**: Angular 18, TypeScript, custom SCSS, Lucide Icons, Glassmorphism UI
* **Backend**: Node.js, Express.js, TypeScript, SQLite
* **Machine Learning**: Python, PyTorch, YOLOv8s (Ultralytics), DINOv2 (Meta), OpenCV, SciPy

---

## 🚀 Setup & Installation (Windows / Mac)

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- Angular CLI (`npm install -g @angular/cli`)

### 1. Setup the Python ML Environment
```bash
python -m venv planogram_env

# Windows
planogram_env\Scripts\activate      

# Mac/Linux
source planogram_env/bin/activate

# Install all dependencies (allows pip to fetch pre-compiled versions)
pip install -r requirements.txt
```
*(Note: YOLOv8s weights (`best_model_yolov8s.pt`) must be present in the `ml-service/notebooks/test/` directory)*

### 2. Start the Backend Server
⚠️ **CRITICAL:** You must activate the Python virtual environment in the terminal before starting the backend, otherwise the machine learning pipeline will fail to find your installed libraries (like OpenCV and YOLO).

Open a new terminal window:
```bash
# First, activate the environment again in this new terminal
planogram_env\Scripts\activate      # Windows
# source planogram_env/bin/activate # Mac/Linux

# Then start the server
cd backend
npm install
npm start
```
*(The backend runs on `http://localhost:3000`)*

### 3. Start the Frontend Application
Open a new terminal window:
```bash
cd frontend
npm install
npm start
```
*(The frontend runs on `http://localhost:4200`)*

---
*Built for the future of retail execution.*
