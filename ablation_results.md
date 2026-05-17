# Backbone Ablation Results

Detector: `retinaface` | Decision: `min(top-5)` | Enroll: 44 images | Test: 25 Doga + 226 Impostor

| Model | EER (%) | t_EER | t for FAR≤5% | FRR (%) | FAR (%) |
|---|---|---|---|---|---|
| **SFace** | 3.8 | 0.590 | 0.620 | 0.0 | 4.0 |
| **ArcFace** | 0.7 | 0.550 | 0.640 | 0.0 | 4.9 |
| **Facenet512** | 0.0 | 0.370 | 0.460 | 0.0 | 4.4 |

## Score Distributions (Summary)

| Model | Doga med | Impostor med | Separation |
|---|---|---|---|
| SFace | 0.421 | 0.800 | +0.379 |
| ArcFace | 0.405 | 0.808 | +0.403 |
| Facenet512 | 0.262 | 0.760 | +0.498 |
