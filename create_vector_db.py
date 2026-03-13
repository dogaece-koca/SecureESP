import os
import shutil
import numpy as np
import chromadb
from deepface import DeepFace

MODEL_NAME = "SFace"
DETECTOR = "retinaface"
DATASET_ROOT = r"C:\Users\doaec\PycharmProjects\ESPSecure\dataset_cropped"
DB_PATH = "my_face_db"


def start_enrollment():
    print(f" Dataset İşleniyor: {DATASET_ROOT}")

    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
        print(" Eski veritabanı silindi.")

    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.create_collection(name="faces", metadata={"hnsw:space": "cosine"})

    klasorler = {"doga": "Doga", "others": "others"}
    toplam_basarili = 0

    for klasor_adi, etiket in klasorler.items():
        hedef_yol = os.path.join(DATASET_ROOT, klasor_adi)
        if not os.path.exists(hedef_yol): continue

        print(f"{klasor_adi} klasörü işleniyor...")
        dosyalar = [f for f in os.listdir(hedef_yol) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        for dosya in dosyalar:
            tam_yol = os.path.join(hedef_yol, dosya)
            try:
                embedding_objs = DeepFace.represent(
                    img_path=tam_yol,
                    model_name=MODEL_NAME,
                    detector_backend=DETECTOR,
                    enforce_detection=True
                )
                embedding = np.array(embedding_objs[0]["embedding"])

                norm_embedding = embedding / np.linalg.norm(embedding)

                collection.add(
                    documents=[etiket],
                    embeddings=[norm_embedding.tolist()],
                    ids=[f"{etiket}_{dosya}"]
                )
                print(f"  Eklendi: {dosya}")
                toplam_basarili += 1
            except:
                print(f"  Atlandı: {dosya} (Yüz saptanamadı)")

    print(f"\nİŞLEM TAMAMLANDI! Toplam {toplam_basarili} yüz kaydedildi.")


if __name__ == "__main__":
    start_enrollment()