# CivicConnect AI

**Intelligent Civic Grievance Management Platform for Hyderabad**

*AI-powered complaint classification · Real-time severity scoring · GHMC integration · Field inspection management*

---

## Overview

**CivicConnect AI** is an end-to-end civic grievance management platform designed to streamline the complaint lifecycle for **Greater Hyderabad Municipal Corporation (GHMC)**. It leverages multi-modal AI — combining NLP text classification with YOLOv8 image recognition — to automatically categorize, prioritize, and route citizen complaints to the correct municipal departments.

The platform serves three user roles:
- **Citizens** — Submit complaints with text descriptions and photographic evidence, receive instant AI analysis, and track resolution in real time.
- **GHMC Supervisors** — Access a command center dashboard with heatmaps, severity analytics, and complaint assignment tools.
- **Field Workers** — Perform on-site inspections with GPS-tagged photo capture and AI-assisted issue classification.

## Key Features

| Module | Description |
|---|---|
| **Multi-Modal Classification** | Fuses NLP text analysis (TF-IDF + LinearSVC) with YOLOv8 image classification. Smart override logic handles edge cases like sewage misclassification. |
| **AI Severity Scoring** | 0–100 scoring engine combining keyword analysis, image confidence, complaint duration, and community duplicate signals. Maps to GHMC's official 4-tier action levels. |
| **Duplicate Detection** | Perceptual hashing (pHash) identifies visually similar photos. Combined with text cosine similarity and location matching for community-level deduplication. |
| **GHMC Integration** | Professional report generation with HYD-VIGIL IDs, 8 randomized WhatsApp templates (anti-spam), one-click email/SMS forwarding, and 48-hour escalation timers. |
| **Admin Command Center** | Role-based dashboard with complaint heatmaps, zone-level analytics, worker assignment, and real-time status tracking across 12 GHMC zones. |
| **Field Inspection System** | Mobile-friendly inspection capture with GPS geolocation, AI classification, and severity scoring — directly integrated into the admin workflow. |
| **Ward-Zone GIS Lookup** | 150+ Hyderabad area mappings to official GHMC wards and zones for accurate jurisdictional routing. |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CITIZEN INTERFACE                        │
│              Text Complaint + Image Upload + GPS                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Flask Server  │
                    │    (app.py)     │
                    └───┬────┬───┬───┘
                        │    │   │
          ┌─────────────┘    │   └─────────────┐
          ▼                  ▼                  ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │  Text Model  │  │ Image Model  │  │  Severity    │
   │  TF-IDF+SVC  │  │  YOLOv8-cls  │  │  Engine      │
   │ (joblib)     │  │  (PyTorch)   │  │ (severity.py)│
   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
          │                  │                  │
          └────────┬─────────┘                  │
                   ▼                            │
          ┌────────────────┐                    │
          │ Fusion Engine  │◄───────────────────┘
          │ (Smart Override│
          │  + pHash Dedup)│
          └───────┬────────┘
                  │
        ┌─────────▼──────────┐
        │   SQLite Database  │
        │  (complaints.db)   │
        └─────────┬──────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌────────┐  ┌─────────┐  ┌──────────┐
│ GHMC   │  │ Admin   │  │ Field    │
│ Forward│  │ Dashboard│ │ Inspect  │
│ Module │  │ + Maps  │  │ System   │
└────────┘  └─────────┘  └──────────┘
```

## Project Structure

```
civic-connect/
│
├── app.py                      # Flask application — routes, classification, fusion logic
├── database.py                 # SQLite ORM — complaints, admin users, field inspections
├── severity.py                 # AI severity scoring engine (0–100 scale)
├── duplicate_detector.py       # Text + location + pHash duplicate detection
├── ghmc_integration.py         # GHMC forwarding — WhatsApp, email, SMS templates
│
├── models/
│   ├── text_model.joblib       # Trained TF-IDF + LinearSVC text classifier
│   └── yolov8n-cls.pt          # YOLOv8 nano classification base weights
│
├── data/
│   ├── authority_mapping.csv   # GHMC department contacts by area and issue type
│   ├── solution_knowledge_base.csv  # Citizen + authority resolution steps
│   └── civic_complaint_scripts_1000.csv  # Training dataset (2100 samples, 6 classes)
│
├── templates/
│   ├── index.html              # Citizen complaint submission form
│   ├── result.html             # AI analysis results + forwarding options
│   ├── tracker.html            # Complaint tracking + escalation status
│   ├── dashboard.html          # Public analytics dashboard
│   ├── about.html              # Platform information page
│   ├── admin_login.html        # GHMC personnel authentication
│   ├── admin_dashboard.html    # Supervisor command center + heatmap
│   ├── field_inspect.html      # Mobile field inspection form
│   └── field_inspections_dashboard.html  # Inspection overview + map
│
├── static/
│   ├── style.css               # Application stylesheet
│   └── uploads/                # User-uploaded complaint images
│
├── scripts/
│   ├── data_gen.py             # Synthetic training data generator
│   ├── train_model.py          # Text classifier training pipeline
│   ├── train_image_model.py    # YOLOv8 image classifier training
│   └── prepare_dataset.py      # Image dataset structure validator
│
├── image_dataset/              # YOLOv8 training images (train/valid/test splits)
├── runs/                       # YOLOv8 training outputs and fine-tuned weights
├── requirements.txt            # Python dependencies
└── .gitignore
```

## Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+, Flask 3.x |
| **NLP Pipeline** | scikit-learn (TF-IDF vectorizer + LinearSVC) |
| **Image Classification** | YOLOv8 (Ultralytics), PyTorch |
| **Duplicate Detection** | imagehash (perceptual hashing), Pillow |
| **Database** | SQLite 3 with WAL journaling |
| **Frontend** | HTML5, CSS3, JavaScript, Leaflet.js (heatmaps) |
| **Integration** | WhatsApp API (deep links), SMTP (email), SMS |

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip package manager
- (Optional) CUDA-compatible GPU for image model training

### Installation

**1. Clone the repository**
```bash
git clone <repository-url>
cd civic-connect
```

**2. Create and activate a virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

**3. Install dependencies**

For the core platform (text classification only):
```bash
pip install -r requirements.txt
```

For full image classification support, uncomment the optional dependencies in `requirements.txt` and install:
```bash
pip install flask pandas scikit-learn joblib numpy torch ultralytics opencv-python imagehash Pillow
```

**4. Initialize the database and launch**
```bash
python app.py
```

The application will be available at `http://127.0.0.1:5000`.

### Default Admin Credentials

| Role | Username | Password |
|---|---|---|
| Supervisor | `supervisor` | `admin123` |
| Field Worker (Khairatabad) | `worker_khairatabad` | `field123` |
| Field Worker (Kukatpally) | `worker_kukatpally` | `field123` |
| Field Worker (Charminar) | `worker_charminar` | `field123` |
| Field Worker (Secunderabad) | `worker_secunderabad` | `field123` |

> **Note:** These are seeded automatically on first run. Change passwords before any production deployment.

## Model Training

### Text Classifier

The text classification model is pre-trained and included at `models/text_model.joblib`. To retrain:

```bash
# 1. (Optional) Regenerate training data
python scripts/data_gen.py

# 2. Train the model
python scripts/train_model.py
```

This produces a TF-IDF + LinearSVC pipeline trained on 2,100 synthetic complaints across 6 categories.

### Image Classifier

```bash
# 1. Validate dataset structure
python scripts/prepare_dataset.py

# 2. Train YOLOv8 (requires GPU recommended)
python scripts/train_image_model.py
```

The trained weights are saved to `runs/classify/train/weights/best.pt` and automatically loaded by the application.

## Issue Categories

| Category | Description | Example |
|---|---|---|
| `pothole_road_damage` | Road surface damage, potholes, cracks | *"Deep pothole on main road causing accidents"* |
| `garbage` | Solid waste, overflowing bins, illegal dumping | *"Garbage piling up near bus stop for 3 days"* |
| `sewage_overflow` | Drain blockages, manhole issues, sewer leaks | *"Sewage overflowing from broken manhole"* |
| `waterlogging` | Flooding, stagnant water, poor drainage | *"Knee-deep water after yesterday's rain"* |
| `streetlight_or_electricity` | Non-functional lights, dangerous wiring | *"Street lights off on entire road at night"* |
| `others` | Stray animals, encroachment, traffic signals | *"Stray dogs attacking people near school"* |

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Citizen complaint submission form |
| `/analyze` | POST | Submit complaint for AI analysis |
| `/track` | GET/POST | Track complaint by ID |
| `/dashboard` | GET | Public analytics dashboard |
| `/about` | GET | Platform information |
| `/api/stats` | GET | JSON — aggregate complaint statistics |
| `/api/complaint/<id>` | GET | JSON — single complaint details |
| `/admin/login` | GET/POST | Administrator authentication |
| `/admin/dashboard` | GET | GHMC command center |
| `/admin/inspect` | GET/POST | Field inspection submission |
| `/admin/inspections` | GET | Inspection dashboard |
| `/api/admin/complaints` | GET | JSON — all complaints with coordinates |
| `/api/admin/inspections` | GET | JSON — all field inspections |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | `civic-connect-dev-key` | Session encryption key |
| `FLASK_RUN_HOST` | `127.0.0.1` | Server bind address |
| `FLASK_RUN_PORT` | `5000` | Server port |

## Coverage

The platform includes pre-configured GIS mappings for **150+ areas** across all **12 official GHMC zones**:

Kukatpally · Serilingampally · Quthbullapur · Khairatabad · Secunderabad · Malkajgiri · Uppal · LB Nagar · Shamshabad · Rajendranagar · Charminar · Golconda

## License

This project is developed for academic and research purposes. All GHMC contact information and zone mappings are sourced from publicly available municipal data.

---

**CivicConnect AI** — *Empowering citizens. Enabling governance.*
