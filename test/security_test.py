import os
import requests
import hmac
import hashlib

URL = "http://127.0.0.1:8080/upload"
SECRET_KEY = b"Doga_Project_Secret_Key_2026"

AUTHORIZED_DIR = "test_doga"
UNAUTHORIZED_DIR = "test_yabanci"
TEST_LIMITI = 200

def send_image(image_path):
    with open(image_path, "rb") as f:
        image_data = f.read()

    signature = hmac.new(SECRET_KEY, image_data, hashlib.sha256).hexdigest()
    headers = {
        'X-Signature': signature,
        'Content-Type': 'application/octet-stream',
        'X-Filename': os.path.basename(image_path),
    }

    try:
        response = requests.post(URL, data=image_data, headers=headers)
        return response.status_code, response.text
    except requests.exceptions.RequestException as e:
        return 0, str(e)


def run_security_tests():
    print("🛡️ AKADEMİK GÜVENLİK TESTLERİ BAŞLIYOR (FAR & FRR)...")
    print("=" * 60)

    # --- 2. FAR (False Acceptance Rate) TESTİ ---
    print(f"\n▶️ FAR TESTİ: '{UNAUTHORIZED_DIR}' klasöründeki yabancı fotoğraflar deneniyor...")
    far_hatalari = 0
    yabanci_fotolari = [f for f in os.listdir(UNAUTHORIZED_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))][
                       :TEST_LIMITI]

    if not yabanci_fotolari:
        print(f"❌ HATA: '{UNAUTHORIZED_DIR}' klasöründe fotoğraf bulunamadı!")
    else:
        for i, dosya in enumerate(yabanci_fotolari):
            tam_yol = os.path.join(UNAUTHORIZED_DIR, dosya)
            status, text = send_image(tam_yol)

            if status == 200 or "GRANTED" in text:
                far_hatalari += 1
                durum_mesaji = "❌ ONAYLANDI (KRİTİK GÜVENLİK HATASI!)"
            else:
                durum_mesaji = "✅ REDDEDİLDİ (BAŞARILI)"

            print(f"[{i + 1}/{len(yabanci_fotolari)}] {dosya} -> {durum_mesaji}")

    # --- SONUÇLARI HESAPLA ---

    toplam_yabanci = len(yabanci_fotolari)
    # --- 1. FRR (False Rejection Rate) TESTİ ---
    print(f"\n▶️ FRR TESTİ: '{AUTHORIZED_DIR}' klasöründeki yetkili fotoğraflar deneniyor...")
    frr_hatalari = 0
    doga_fotolari = [f for f in os.listdir(AUTHORIZED_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))][
                    :TEST_LIMITI]

    if not doga_fotolari:
        print(f"❌ HATA: '{AUTHORIZED_DIR}' klasöründe fotoğraf bulunamadı!")
    else:
        for i, dosya in enumerate(doga_fotolari):
            tam_yol = os.path.join(AUTHORIZED_DIR, dosya)
            status, text = send_image(tam_yol)

            if status != 200 or "DENIED" in text:
                frr_hatalari += 1
                durum_mesaji = "❌ REDDEDİLDİ (HATA)"
            else:
                durum_mesaji = "✅ ONAYLANDI (BAŞARILI)"

            print(f"[{i + 1}/{len(doga_fotolari)}] {dosya} -> {durum_mesaji}")

    toplam_doga = len(doga_fotolari)

    print("\n" + "=" * 60)
    print("📊 MAKALE İÇİN KESİN GÜVENLİK METRİKLERİ")
    print("=" * 60)

    if toplam_doga > 0 and toplam_yabanci > 0:
        frr_yuzde = (frr_hatalari / toplam_doga) * 100
        far_yuzde = (far_hatalari / toplam_yabanci) * 100

        print(
            f"Toplam Test Edilen Fotoğraf: {toplam_doga + toplam_yabanci} ({toplam_doga} Yetkili, {toplam_yabanci} Yabancı)")
        print("-" * 60)
        print(f"Yanlış Reddetme (FRR):  {frr_hatalari} / {toplam_doga}  ->  %{frr_yuzde:.1f}")
        print(f"Yanlış Kabul (FAR):     {far_hatalari} / {toplam_yabanci}  ->  %{far_yuzde:.1f}")
        print("=" * 60)


if __name__ == '__main__':
    if not os.path.exists(AUTHORIZED_DIR): os.makedirs(AUTHORIZED_DIR)
    if not os.path.exists(UNAUTHORIZED_DIR): os.makedirs(UNAUTHORIZED_DIR)
    run_security_tests()