import os
import hmac
import hashlib
from flask import Flask, request, render_template_string
import cloudinary
import cloudinary.uploader
import cloudinary.api

app = Flask(__name__)

# --- AYARLAR (Render Environment Variables'dan çekecek) ---
# Bunları kodun içine GÖMMÜYORUZ, Render panelinden gireceğiz (Güvenlik için)
SECRET_KEY = os.environ.get("MY_SECRET_KEY", "Varsayilan_Guvenli_Olmayan_Key").encode()

cloudinary.config(
  cloud_name = os.environ.get("CLOUD_NAME"),
  api_key = os.environ.get("CLOUD_API_KEY"),
  api_secret = os.environ.get("CLOUD_API_SECRET")
)

@app.route('/')
def gallery():
    try:
        response = cloudinary.api.resources(
            type="upload",
            prefix="secureesp/",
            max_results=20,
            direction="desc"
        )
        images = response.get('resources', [])
    except Exception as e:
        return f"Cloudinary Baglanti Hatasi: {str(e)}"

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Secure Cloud</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #1a1a1a; color: #ddd; text-align: center; padding: 20px; }
            h1 { color: #fff; margin-bottom: 30px; }
            .grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }
            .card { 
                background: #2a2a2a; 
                padding: 15px; 
                border-radius: 12px; 
                width: 300px; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.5); 
                transition: transform 0.2s;
            }
            .card:hover { transform: translateY(-5px); }
            img { width: 100%; border-radius: 8px; margin-bottom: 10px; }
            a { 
                display: inline-block; 
                margin-top: 10px; 
                color: #00d2ff; 
                text-decoration: none; 
                border: 1px solid #00d2ff; 
                padding: 5px 15px; 
                border-radius: 20px; 
            }
            a:hover { background: #00d2ff; color: #1a1a1a; }
            .status { 
                color: #00ff88; 
                font-weight: bold; 
                font-size: 0.9em; 
                margin: 10px 0; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                gap: 5px;
            }
            .timestamp { color: #888; font-size: 0.8em; }
        </style>
    </head>
    <body>
        <h1>Cloud Gallery</h1>
        <div class="grid">
            {% for img in images %}
            <div class="card">
                <img src="{{ img.secure_url }}" loading="lazy">
                <div class="status">
                    <span></span> Signature Verified
                </div>
                <p class="timestamp">{{ img.created_at }}</p>
                <a href="{{ img.secure_url }}" target="_blank">Full Size</a>
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
            return "Eksik Veri", 400

        # HMAC Doğrulama
        calculated_signature = hmac.new(SECRET_KEY, image_data, hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_signature, received_signature):
            # Cloudinary'ye Yükle
            upload_result = cloudinary.uploader.upload(
                image_data,
                folder = "secureesp", # Cloudinary içinde klasör açar
                public_id = f"secure_img_{calculated_signature[:10]}"
            )
            return "SUCCESS: Uploaded to Cloud", 200
        else:
            return "ALERT: Fake Image!", 403

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)