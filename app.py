import os
import io
import hmac
import hashlib
import threading
import uuid
from collections import deque
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import cv2
import numpy as np
from flask import Flask, request, render_template_string, send_file, abort

import chromadb
from deepface import DeepFace

import cloudinary
import cloudinary.uploader


SECRET_KEY = os.environ.get("ESP_SECRET_KEY", "Doga_Project_Secret_Key_2026").encode()
THRESHOLD = float(os.environ.get("ESP_THRESHOLD", "0.55"))
DETECTOR = os.environ.get("ESP_DETECTOR", "retinaface")
DB_PATH = "my_face_db"
MODEL_NAME = "Facenet512"
TOP_K = 5
GALLERY_LIMIT = 50

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
)

app = Flask(__name__)

# Bellek-içi galeri: (id, jpg_bytes, status, person, score, time_str) — en yeni başta
GALLERY = deque(maxlen=GALLERY_LIMIT)
GALLERY_LOCK = threading.Lock()

chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_collection(name="faces")
print(f"DB hazır: {collection.count()} kayıt | Threshold: {THRESHOLD} | Detector: {DETECTOR}")

# Modelleri başlangıçta yükle (her çağrıda yeniden yüklemeyi engeller)
print(f"Modeller önyüklenecek: {MODEL_NAME} + {DETECTOR} (ilk seferde 10-30 sn)")
try:
    DeepFace.build_model(MODEL_NAME)
    print(f"  {MODEL_NAME} yüklendi.")
except Exception as e:
    print(f"  {MODEL_NAME} preload hatası: {e}")
# RetinaFace'i de bir kez çağırarak ön-belleğe al
import numpy as _np
_dummy = _np.zeros((224, 224, 3), dtype=_np.uint8)
try:
    DeepFace.represent(img_path=_dummy, model_name=MODEL_NAME,
                       detector_backend=DETECTOR, enforce_detection=False, align=True)
    print(f"  {DETECTOR} ısındı.")
except Exception:
    pass
print("Sunucu hazır.")


def predict(img_bgr):
    try:
        objs = DeepFace.represent(
            img_path=img_bgr, model_name=MODEL_NAME,
            detector_backend=DETECTOR, enforce_detection=True, align=True,
        )
    except ValueError:
        return "DENIED", "Yüz Saptanamadı", None, []

    emb = np.array(objs[0]["embedding"], dtype=np.float32)
    emb = emb / np.linalg.norm(emb)
    res = collection.query(query_embeddings=[emb.tolist()],
                           n_results=min(TOP_K, collection.count()))
    dists = [float(d) for d in res["distances"][0]]
    score = min(dists)
    status = "GRANTED" if score < THRESHOLD else "DENIED"
    person = "Doga" if status == "GRANTED" else "Yabancı"
    return status, person, score, dists


def upload_bg(image_data, public_id, status, score):
    if not os.environ.get("CLOUDINARY_API_SECRET"):
        return
    try:
        cloudinary.uploader.upload(
            image_data, folder="secureesp", public_id=public_id,
            context={"status": status,
                     "score": f"{score:.4f}" if score is not None else "NA",
                     "threshold": f"{THRESHOLD:.3f}",
                     "model": MODEL_NAME, "detector": DETECTOR},
            tags=[status.lower()],
        )
        print(f"Cloudinary yüklendi: secureesp/{public_id}")
    except Exception as e:
        print(f"Cloudinary hata: {e}")


@app.route("/upload", methods=["POST"])
def upload_file():
    image_data = request.data
    sig = request.headers.get("X-Signature")
    if not image_data or not sig:
        return "Eksik Veri", 400

    calc = hmac.new(SECRET_KEY, image_data, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, str(sig)):
        return "İmza Uyuşmuyor!", 403

    img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return "Geçersiz Görüntü", 400

    import time as _t
    _srv_t0 = _t.perf_counter()
    status, person, score, dists = predict(img)
    server_ms = int((_t.perf_counter() - _srv_t0) * 1000)

    from urllib.parse import unquote
    filename = unquote(request.headers.get("X-Filename", ""))
    print(f"[{status}] {person} | score={score} | server_ms={server_ms} | {filename}")

    # Bellek-içi galeriye ekle (en yeni başta)
    photo_id = uuid.uuid4().hex[:8]
    entry = {
        "id": photo_id,
        "jpg": image_data,
        "filename": filename,
        "status": status,
        "person": person,
        "score": score,
        "k_distances": dists,
        "server_ms": server_ms,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with GALLERY_LOCK:
        GALLERY.appendleft(entry)

    # Cloudinary'e arka planda arşivle (galerinin çalışması buna bağlı değil)
    pid = f"{status}_{person}_{calc[:6]}"
    threading.Thread(target=upload_bg,
                     args=(image_data, pid, status, score),
                     daemon=True).start()

    return f"ACCESS {status}", 200 if status == "GRANTED" else 403


@app.route("/photo/<pid>")
def serve_photo(pid):
    """Bellek-içi galeriden tek bir fotoğrafı sunar (tarayıcıda cache'lenir)."""
    with GALLERY_LOCK:
        for e in GALLERY:
            if e["id"] == pid:
                resp = send_file(io.BytesIO(e["jpg"]), mimetype="image/jpeg")
                resp.headers["Cache-Control"] = "public, max-age=86400, immutable"
                return resp
    abort(404)


@app.route("/api/count")
def api_count():
    """Galeri durumu — sayfa bunu poll edip değişiklik olduğunda yenileniyor."""
    with GALLERY_LOCK:
        latest_id = GALLERY[0]["id"] if GALLERY else ""
        return {"count": len(GALLERY), "latest": latest_id}


def _csv_safe(v):
    s = "" if v is None else str(v)
    if any(c in s for c in [",", '"', "\n", "\r"]):
        s = '"' + s.replace('"', '""') + '"'
    return s


@app.route("/export.csv")
def export_csv():
    """Bu oturumun tüm kararlarını CSV olarak indir."""
    with GALLERY_LOCK:
        items = list(GALLERY)
    items.reverse()  # eskiden yeniye

    rows = ["timestamp,filename,id,status,person,score,threshold,model,detector,k_distances"]
    for e in items:
        k_str = ";".join(f"{d:.4f}" for d in e.get("k_distances", []))
        score = e.get("score")
        rows.append(",".join(_csv_safe(x) for x in [
            e["time"],
            e.get("filename", ""),
            e["id"],
            e["status"],
            e["person"],
            f"{score:.4f}" if score is not None else "NA",
            f"{THRESHOLD:.3f}",
            MODEL_NAME,
            DETECTOR,
            k_str,
        ]))

    body = "\n".join(rows) + "\n"
    fname = f"secureesp_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return body, 200, {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": f'attachment; filename="{fname}"',
    }


@app.route("/")
def gallery():
    with GALLERY_LOCK:
        items = list(GALLERY)

    html = """
    <!DOCTYPE html><html><head><title>SecureESP</title>
    <style>
      body{font-family:sans-serif;background:#121212;color:#eee;text-align:center;padding:20px}
      .panel{display:inline-block;border:2px dashed #444;padding:20px;border-radius:15px;background:#1a1a1a;margin-bottom:30px}
      .g{color:#0f8;border:1px solid #0f8;padding:8px;border-radius:5px;display:inline-block}
      .d{color:#f44;border:1px solid #f44;padding:8px;border-radius:5px;display:inline-block}
      .grid{display:flex;flex-wrap:wrap;justify-content:center;gap:20px}
      .card{background:#1e1e1e;padding:10px;border-radius:12px;width:240px;border:1px solid #333}
      img{width:100%;border-radius:8px}
      .meta{font-size:.75em;color:#aaa;margin-top:6px}
    </style></head><body>
    <h1>SecureESP</h1>
    {% if items %}
      <p style="margin-top:-10px"><a href="/export.csv" style="color:#7af">CSV indir ({{ items|length }} kayıt)</a></p>
      {% set latest = items[0] %}
      <div class="panel">
        <h3 style="margin:0 0 12px;color:#888">Son Karar</h3>
        <img src="/photo/{{ latest.id }}" style="max-width:320px;border-radius:8px;margin-bottom:12px">
        {% if latest.status == 'GRANTED' %}<div class="g">ONAYLANDI: {{ latest.person }}</div>
        {% else %}<div class="d">REDDEDİLDİ: {{ latest.person }}</div>{% endif %}
        <div class="meta">
          {% if latest.filename %}<b>{{ latest.filename }}</b><br>{% endif %}
          skor: {% if latest.score is not none %}{{ '%.4f'|format(latest.score) }}{% else %}NA{% endif %} / eşik: {{ '%.3f'|format(thr) }} | {{ latest.time }}
        </div>
      </div>
      <h2 style="margin-top:40px;color:#bbb">Bu oturumun tüm kayıtları ({{ items|length }})</h2>
      <div class="grid">
        {% for e in items %}
          <div class="card">
            <img src="/photo/{{ e.id }}" loading="lazy">
            {% if e.status == 'GRANTED' %}<div class="g">ONAYLANDI</div>
            {% else %}<div class="d">REDDEDİLDİ</div>{% endif %}
            <div class="meta">
              {% if e.filename %}<b>{{ e.filename }}</b><br>{% endif %}
              skor: {% if e.score is not none %}{{ '%.4f'|format(e.score) }}{% else %}NA{% endif %} | {{ e.time.split(' ')[1] if ' ' in e.time else e.time }}
            </div>
          </div>
        {% endfor %}
      </div>
    {% else %}
      <p style="color:#666;margin-top:40px">Henüz fotoğraf yüklenmedi.</p>
    {% endif %}
    <script>
      let lastLatest = "{{ items[0].id if items else '' }}";
      let lastCount = {{ items|length }};
      setInterval(async () => {
        try {
          const r = await fetch("/api/count");
          const d = await r.json();
          if (d.latest !== lastLatest || d.count !== lastCount) {
            location.reload();
          }
        } catch(e) {}
      }, 2000);
    </script>
    </body></html>
    """
    return render_template_string(html, items=items, thr=THRESHOLD)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
