# IoT-Based Biometric Access Control System

> **ZINC 2026** — Doga Ece Koca & Prof. Dr. Mehmet Hilal Özcanhan  
> Dokuz Eylül University, Computer Engineering, İzmir, Türkiye

Low-cost, cryptographically secured face recognition access control system built on ESP32-CAM + Flask + ChromaDB.

---

## Overview

This system is the **first phase** of a multimodal biometric framework. It combines:

- **Edge-side** cryptographic signing (HMAC-SHA256) on ESP32-CAM
- **Server-side** deep learning face recognition (RetinaFace + Facenet512)
- **Vector database** identity matching (ChromaDB, cosine similarity)
- **Cloud archiving** of access logs (Cloudinary)

---

## Architecture

```
┌─────────────────────────────────┐
│         IoT Edge Unit           │
│  ESP32-CAM + OV2640 + HC-SR04  │
│  HMAC-SHA256 Signing            │
└────────────┬────────────────────┘
             │ HTTP POST (Port 8080)
             │ Header: X-Signature
             ▼
┌─────────────────────────────────┐
│       Local Server (Flask)      │
│  1. HMAC Verification           │
│  2. RetinaFace Detection        │
│  3. Facenet512 Embedding        │
│  4. ChromaDB Vector Query       │
└────────────┬────────────────────┘
             │ HTTPS (Port 443)
             ▼
┌─────────────────────────────────┐
│       Cloud (Cloudinary)        │
│  Access logs + image archive    │
└─────────────────────────────────┘
```

---

## Hardware

| Component | Model | Purpose |
|-----------|-------|---------|
| IoT Edge Unit | AI-Thinker ESP32-CAM | Dual-core LX6 @ 240 MHz, 4MB PSRAM |
| Camera | OV2640 | JPEG capture, VGA resolution |
| Distance Sensor | HC-SR04 | 2–400 cm, ±3 mm accuracy |
| Button | Mechanical push-button | Photo trigger (GPIO 2) |
| Indicator | 5mm LED | Distance feedback (GPIO 4) |
| Power | 5V/2A external supply | Prevents brownout on Wi-Fi TX |

### GPIO Pin Assignment

| Component | Component Pin | ESP32-CAM Pin |
|-----------|--------------|---------------|
| HC-SR04 | VCC | 5V |
| HC-SR04 | GND | GND |
| HC-SR04 | TRIG | GPIO 13 |
| HC-SR04 | ECHO | GPIO 12 |
| Push-Button | Terminal 1 | GPIO 2 |
| Push-Button | Terminal 2 | GND |
| 5mm LED | Anode | GPIO 4 |
| 5mm LED | Cathode | GND |

---

## Software Stack

| Layer | Technology |
|-------|-----------|
| Edge firmware | C++ (Arduino), mbedTLS |
| Backend | Python 3.9, Flask |
| Face detection | RetinaFace (via DeepFace) |
| Face recognition | Facenet512 (via DeepFace) |
| Vector DB | ChromaDB (cosine distance) |
| Cloud logging | Cloudinary |

---

## Project Structure

```
project/
├── CameraWebServer/          # Arduino firmware for ESP32-CAM
│   └── CameraWebServer.ino
├── app.py                    # Flask server (main backend)
├── create_vector_db.py       # Enroll faces into ChromaDB
├── dataset_cropped/
│   └── doga/                 # Enrollment photos
├── my_face_db/               # ChromaDB persistent storage (auto-created)
├── .env                      # Environment variables (not committed)
└── README.md
```

---

## Setup

### 1. Clone & Install Dependencies

```bash
pip install flask deepface chromadb cloudinary python-dotenv opencv-python numpy
```

> RetinaFace and Facenet512 model weights are downloaded automatically on first run (~300 MB).

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
ESP_SECRET_KEY=your_secret_key_here
ESP_THRESHOLD=0.55
ESP_DETECTOR=retinaface
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

> ⚠️ **Never commit `.env` to version control.** The `ESP_SECRET_KEY` must match the `secretKey` value flashed on the ESP32-CAM.

### 3. Enroll Faces into the Database

Place cropped face images into `dataset_cropped/name/` (`.jpg` or `.png`), then run:

```bash
python create_vector_db.py
```

This will:
- Process all images with RetinaFace + Facenet512
- Normalize embeddings (L2)
- Store them in ChromaDB (`my_face_db/`)
- Report skipped images (no face detected)

### 4. Flash the ESP32-CAM

Open `CameraWebServer/CameraWebServer.ino` in Arduino IDE and set:

```cpp
const char* ssid     = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
String serverUrl     = "http://YOUR_SERVER_IP:8080/upload";
const char* secretKey = "YOUR_SECRET_KEY";  // Must match .env
```

Select board: **AI Thinker ESP32-CAM**, then upload.

### 5. Start the Flask Server

```bash
python app.py
```

Server starts on `http://0.0.0.0:8080`. Open in browser to view the live dashboard.

---

## How It Works

### Edge Device Flow

1. HC-SR04 measures distance every 2 seconds (filtered median of 5 samples)
2. LED turns ON when user is 30–80 cm from camera
3. Button press triggers photo capture (OV2640, UXGA if PSRAM available)
4. Image is signed with HMAC-SHA256 using the shared secret key
5. Signed image is sent via HTTP POST with `X-Signature` header

### Server Flow

1. **HMAC Verification** — signature mismatch → `403 Forbidden`, no AI runs
2. **Face Detection** — RetinaFace locates face and landmarks
3. **Embedding** — Facenet512 produces a 512-dim feature vector, L2-normalized
4. **Vector Query** — ChromaDB returns top-K cosine distances
5. **Decision** — `score < THRESHOLD` → `GRANTED`, else `DENIED`
6. **Logging** — Result + image archived to Cloudinary asynchronously
7. **Response** — `ACCESS GRANTED` or `ACCESS DENIED` sent back to ESP32-CAM

### LED Feedback on ESP32

| Pattern | Meaning |
|---------|---------|
| Solid ON | Distance OK, ready to capture |
| OFF | Out of range |
| Solid ON 2 sec | Access GRANTED |
| 3× fast blink | Access DENIED |

---

## Dashboard

Access `http://YOUR_SERVER_IP:8080` in a browser:

- Live view of the latest access attempt
- Full session history (photo grid)
- CSV export of all decisions (`/export.csv`)
- Auto-refreshes every 2 seconds via polling

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ESP_SECRET_KEY` | — | Shared HMAC secret (required) |
| `ESP_THRESHOLD` | `0.35` | Cosine distance cutoff for GRANTED |
| `ESP_DETECTOR` | `retinaface` | DeepFace detector backend |
| `MIN_DISTANCE` | `30` cm | Minimum valid user distance |
| `MAX_DISTANCE` | `80` cm | Maximum valid user distance |
| `TOP_K` | `5` | Number of ChromaDB neighbors to query |
| `GALLERY_LIMIT` | `50` | Max in-memory photos per session |

---

## Security Notes

- HMAC-SHA256 prevents man-in-the-middle attacks by binding the image payload to a secret known only to the edge device and server
- No face analysis occurs before signature verification
- The shared secret key should be long, random, and rotated periodically
- For production deployment, use HTTPS (TLS) between edge and server

---

## Future Work

- **EEG Integration** — Liveness detection via electroencephalography signals to prevent spoofing attacks (Phase 2)
- **Multi-user enrollment** — Extend beyond single-user ChromaDB collection
- **Performance benchmarking** — Latency, FAR/FRR metrics under controlled conditions
- **TLS on edge** — Encrypted transport between ESP32-CAM and server

---

## Citation

If you use this work, please cite:

```
D. E. Koca and M. H. Özcanhan, "IoT-Based Biometric Access Control System,"
in Proc. ZINC 2026, IEEE, 2026.
```

---

## License

This project is for academic research purposes. All rights reserved by the authors.
