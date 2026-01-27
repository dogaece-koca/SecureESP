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

SECRET_KEY = os.environ.get("MY_SECRET_KEY", "Varsayilan_Guvenli_Olmayan_Key").encode()
DB_PATH = "my_face_db"
MODEL_NAME = "VGG-Face"

cloudinary.config(
    cloud_name=os.environ.get("CLOUD_NAME"),
    api_key=os.environ.get("CLOUD_API_KEY"),
    api_secret=os.environ.get("CLOUD_API_SECRET")
)

try:
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    collection = chroma_client.get_collection(name="faces")
    print("Database Ready")
except Exception as e:
    print(f"VDatabase Error: {e}")
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
        return f"Cloudinary Connection Error: {str(e)}"

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Access Log</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #121212; color: #e0e0e0; text-align: center; padding: 20px; }
            h1 { color: #fff; margin-bottom: 30px; }
            .grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }

            .card { 
                background: #1e1e1e; 
                padding: 10px; 
                border-radius: 12px; 
                width: 280px; 
                box-shadow: 0 4px 10px rgba(0,0,0,0.5); 
                transition: transform 0.2s;
                border: 1px solid #333;
            }
            .card:hover { transform: translateY(-5px); }
            img { width: 100%; border-radius: 8px; margin-bottom: 10px; }

            .status-granted { color: #00ff88; font-weight: bold; border: 1px solid #00ff88; padding: 5px; border-radius: 5px; background: rgba(0, 255, 136, 0.1); }
            .status-denied { color: #ff4444; font-weight: bold; border: 1px solid #ff4444; padding: 5px; border-radius: 5px; background: rgba(255, 68, 68, 0.1); }

            .timestamp { color: #888; font-size: 0.8em; margin-top: 5px;}
        </style>
    </head>
    <body>
        <h1>SecureESP Access Logs</h1>
        <div class="grid">
            {% for img in images %}
            <div class="card">
                <img src="{{ img.secure_url }}" loading="lazy">

                {% if 'GRANTED' in img.public_id %}
                    <div class="status-granted">
                        <span>🔓</span> ACCESS GRANTED<br>
                        <small>Tanınan Kişi</small>
                    </div>
                {% else %}
                    <div class="status-denied">
                        <span>🚫</span> ACCESS DENIED<br>
                        <small>Tanımsız / Saçma</small>
                    </div>
                {% endif %}

                <p class="timestamp">{{ img.created_at }}</p>
                <a href="{{ img.secure_url }}" target="_blank" style="color:#aaa; text-decoration:none;">Orjinal</a>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, images=images)


@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        image_data = request.data
        received_signature = request.headers.get('X-Signature')

        if not image_data or not received_signature:
            return "Insufficient Data", 400

        calculated_signature = hmac.new(SECRET_KEY, image_data, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_signature, received_signature):
            return "ALERT: Fake Image!", 403

        if collection is None:
            return "Server Error: no DB", 500

        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        identified_person = "Unknown"
        access_status = "DENIED"

        try:
            embedding_objs = DeepFace.represent(
                img_path=img,
                model_name=MODEL_NAME,
                enforce_detection=False
            )
            target_embedding = embedding_objs[0]["embedding"]

            results = collection.query(
                query_embeddings=[target_embedding],
                n_results=1
            )

            if results['ids'][0]:
                distance = results['distances'][0][0]
                person_name = results['documents'][0][0]

                if distance < 22.0 and person_name != "others":
                    identified_person = person_name
                    access_status = "GRANTED"
                else:
                    identified_person = "Intruder"

        except Exception as e:
            print(f"Face Recognition Error: {e}")
            identified_person = "NoFace"

        public_id_format = f"{access_status}_{identified_person}_{calculated_signature[:6]}"

        upload_result = cloudinary.uploader.upload(
            image_data,
            folder="secureesp",
            public_id=public_id_format
        )

        if access_status == "GRANTED":
            return f"ACCESS GRANTED: {identified_person}", 200
        else:
            return "ACCESS DENIED", 403

    except Exception as e:
        return f"Error: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True)