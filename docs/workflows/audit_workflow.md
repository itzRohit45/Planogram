# Audit Workflow

This document explains the data flow from the moment a user uploads an audit image until the final compliance report is rendered on the screen.

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Frontend as Angular UI
    participant Backend as Node.js Express
    participant DB as SQLite
    participant Python as ML Engine (Python)

    User->>Frontend: Selects Baseline and clicks "Take Photo"
    Frontend->>Backend: POST /api/audits (Multipart Form)
    Backend->>Filesystem: Saves raw Audit Image
    Backend->>DB: Fetches Baseline metadata & image path
    Backend->>Python: Spawns child process (audit_engine.py)
    
    activate Python
    Note over Python: 1. YOLOv8s Detection
    Python->>Python: Detect bounding boxes in Baseline & Audit
    
    Note over Python: 2. DINOv2 Feature Extraction
    Python->>Python: Extract 384d embedding for each crop
    
    Note over Python: 3. Heuristic Scoring
    Python->>Python: Calculate Spatial IoU & Color Histogram
    Python->>Python: Combine scores (DINOv2 + IoU + Color)
    
    Note over Python: 4. Hungarian Matching
    Python->>Python: Bipartite graph matching (Baseline <-> Audit)
    Python->>Filesystem: Draw bounding boxes & save visual_report.jpg
    Python-->>Backend: Returns JSON Report (stdout)
    deactivate Python
    
    Backend->>DB: Saves Audit Record (Compliance Score)
    Backend-->>Frontend: HTTP 200 (AuditResponse JSON)
    Frontend->>Frontend: Routes to /report component
    Frontend->>User: Renders glowing bounding boxes and data table
```

### Steps Explained:
1. **Upload**: The user captures an image and it is sent to the Node.js backend.
2. **Execution**: The backend calls the Python script, passing the paths to the Baseline and Audit images.
3. **Detection**: YOLOv8s finds all products on the shelf.
4. **Feature Extraction**: DINOv2 converts those products into deep mathematical representations (embeddings).
5. **Matching**: The Hungarian algorithm matches the products from the baseline to the products on the actual shelf to find exactly what is missing, extra, or incorrectly placed.
6. **Rendering**: The Angular frontend overlays the results as interactive bounding boxes.
