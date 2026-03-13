import os
import hmac
import hashlib
import cv2
import numpy as np
from flask import Flask, request, render_template_string
import cloudinary
import cloudinary.uploader
import cloudinary.api
import chromadb
from deepface import DeepFace

app = Flask(__name__)

# --- AYARLAR ---
SECRET_KEY = "Doga_Project_Secret_Key_2026".encode()
DB_PATH = "my_face_db"
MODEL_NAME = "SFace"

# --- GLOBAL DURUM TAKİBİ ---
last_status = "Bekleniyor..."
last_person = "Hazır"

# Cloudinary Ayarları
cloudinary.config(
    cloud_name="dsm4vyfsx",
    api_key="616628969826829",
    api_secret="RBII1oXquH6GgVVjB0ZHhDMRcBs"
)

# Veritabanı Başlatma
try:
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    collection = chroma_client.get_collection(name="faces")
    print("Veritabanı ve AI Sistemi Hazır")
except Exception as e:
    print(f"Veritabanı Hatası: {e}")
    collection = None


@app.route('/')
def gallery():
    try:
        response = cloudinary.api.resources(
            type="upload",
            prefix="secureesp/",
            max_results=30,
            direction="desc"
        )
        images = response.get('resources', [])
    except Exception as e:
        images = []

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Güvenlik Paneli</title>
        <meta http-equiv="refresh" content="5">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #121212; color: #e0e0e0; text-align: center; padding: 20px; }
            h1 { color: #fff; margin-bottom: 30px; }
            .grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }
            .card { background: #1e1e1e; padding: 10px; border-radius: 12px; width: 280px; border: 1px solid #333; }
            img { width: 100%; border-radius: 8px; margin-bottom: 10px; }
            .status-granted { color: #00ff88; font-weight: bold; border: 1px solid #00ff88; padding: 8px; border-radius: 5px; background: rgba(0, 255, 136, 0.1); display: inline-block; }
            .status-denied { color: #ff4444; font-weight: bold; border: 1px solid #ff4444; padding: 8px; border-radius: 5px; background: rgba(255, 68, 68, 0.1); display: inline-block; }
            .local-debug { margin-bottom: 30px; border: 2px dashed #444; padding: 20px; border-radius: 15px; background: #1a1a1a; display: inline-block; }
        </style>
    </head>
    <body>
        <h1>🛡️ SecureESP Yönetim Paneli</h1>

        <div class="local-debug">
            <h3>Canlı Durum Analizi</h3>
            <img src="/static/son_foto.jpg?t={{ range(1, 10000) | random }}" style="max-width: 300px; display: block; margin: 0 auto 15px; border: 2px solid #333;">

            {% if status == 'GRANTED' %}
                <div class="status-granted">🔓 ERİŞİM ONAYLANDI: {{ person }}</div>
            {% elif status == 'DENIED' %}
                <div class="status-denied">🚫 ERİŞİM REDDEDİLDİ: {{ person }}</div>
            {% else %}
                <div style="color: #aaa;">⏳ {{ status }}</div>
            {% endif %}
        </div>

        <div class="grid">
            {% for img in images %}
            <div class="card">
                <img src="{{ img.secure_url }}" loading="lazy">
                {% if 'GRANTED' in img.public_id %}
                    <div class="status-granted" style="font-size: 0.8em;">🔓 ONAYLANDI<br><small>{{ img.public_id.split('_')[1] }}</small></div>
                {% else %}
                    <div class="status-denied" style="font-size: 0.8em;">🚫 REDDEDİLDİ<br><small>Yabancı/Hata</small></div>
                {% endif %}
                <p style="color:#888; font-size:0.7em; margin-top:10px;">{{ img.created_at }}</p>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, images=images, status=last_status, person=last_person)


@app.route('/upload', methods=['POST'])
def upload_file():
    global last_status, last_person
    try:
        image_data = request.data
        received_signature = request.headers.get('X-Signature')

        if not image_data or not received_signature:
            return "Eksik Veri", 400

        calculated_signature = hmac.new(SECRET_KEY, image_data, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_signature, str(received_signature)):
            last_status = "DENIED"
            last_person = "Güvenlik Hatası"
            return "İmza Uyuşmuyor!", 403

        if collection is None:
            return "Veritabanı Yok", 500

        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if not os.path.exists('static'):
            os.makedirs('static')
        cv2.imwrite("static/son_foto.jpg", img)

        identified_person = "Unknown"
        access_status = "DENIED"

        try:
            embedding_objs = DeepFace.represent(
                img_path=img,
                model_name=MODEL_NAME,
                detector_backend="retinaface",
                enforce_detection=True
            )

            raw_embedding = np.array(embedding_objs[0]["embedding"])
            norm_embedding = raw_embedding / np.linalg.norm(raw_embedding)

            results = collection.query(
                query_embeddings=[norm_embedding.tolist()],
                n_results=1
            )

            if results['ids'][0]:
                distance = results['distances'][0][0]
                person_name = results['documents'][0][0]

                print(f"Analiz: {person_name} | Mesafe: {distance:.4f}")

                if distance < 0.50 and person_name != "others":
                    identified_person = person_name
                    access_status = "GRANTED"
                else:
                    identified_person = "Yabancı"
                    access_status = "DENIED"
            else:
                identified_person = "Veri Yok"
                access_status = "DENIED"

        except Exception as e:
            print(f"AI Analiz Hatası: {e}")
            identified_person = "Yüz Saptanamadı"
            access_status = "DENIED"

        last_status = access_status
        last_person = identified_person

        public_id_format = f"{access_status}_{identified_person}_{calculated_signature[:6]}"
        cloudinary.uploader.upload(
            image_data,
            folder="secureesp",
            public_id=public_id_format
        )

        return f"ACCESS {access_status}", 200 if access_status == "GRANTED" else 403

    except Exception as e:
        print(f"Kritik Hata: {e}")
        return f"Error: {str(e)}", 500


if __name__ == '__main__':
    print("Sunucu Başlatılıyor... Port: 8080")
    app.run(host='0.0.0.0', port=8080, debug=True)