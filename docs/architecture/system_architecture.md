# System Architecture

Planogram is designed using a modern microservice-style architecture. This allows the compute-heavy Python machine learning tasks to be decoupled from the real-time Node.js backend.

## High-Level Architecture Diagram

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
        Device[Mobile Camera / Browser]:::frontend
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
        Hungarian[Hungarian Matcher]:::ml
    end

    %% Relationships
    Device -->|Captures Image| A
    A -->|Multipart Upload| B
    B -->|Saves Metadata| DB
    B -->|Saves Images| Files
    B -->|Spawns Child Process| C
    
    C -->|Detects bounding boxes| Yolo
    C -->|Extracts 384d features| Dino
    C -->|Pairs objects| Hungarian
    
    Yolo -.-> C
    Dino -.-> C
    Hungarian -.-> C
    
    C -->|Returns JSON Report| B
    B -->|Sends Report| A
```

### Components:
1. **Frontend (Angular)**: Handles the UI, state routing, and device camera integration.
2. **Backend (Node.js)**: Orchestrates data flow, serves static files, and executes the Python ML scripts as child processes to avoid blocking the main event loop.
3. **ML Engine (Python)**: Uses YOLOv8s to slice up the shelf image into individual product crops, and DINOv2 to compute high-dimensional visual fingerprints for each crop.
