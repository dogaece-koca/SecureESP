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
    # Cloudinary'den son 10 resmi çek
    try:
        response = cloudinary.api.resources(
            type="upload",
            prefix="secureesp/", # Sadece bu projenin klasörü
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
            body { font-family: sans-serif; background: #222; color: white; text-align: center; }
            .grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
            .card { background: #333; padding: 10px; border-radius: 8px; width: 300px; }
            img { width: 100%; border-radius: 5px; }
            a { color: #00d2ff; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1>Bulut Galerisi</h1>
        <div class="grid">
            {% for img in images %}
            <div class="card">
                <img src="{{ img.secure_url }}" loading="lazy">
                <p><small>{{ img.created_at }}</small></p>
                <a href="{{ img.secure_url }}" target="_blank">Tam Boyut</a>
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