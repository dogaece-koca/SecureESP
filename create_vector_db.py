import os
import shutil
import numpy as np
import chromadb
from deepface import DeepFace

ENROLL_DIR = r"C:\Users\doaec\PycharmProjects\ESPSecure\dataset_cropped\doga"

DB_PATH = "my_face_db"
MODEL_NAME = "ArcFace"
DETECTOR = "retinaface"

def get_embedding(path):
    try:
        objs = DeepFace.represent(
            img_path=path,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR,
            enforce_detection=True,
            align=True,
        )
    except ValueError:
        return None
    if not objs:
        return None
    v = np.array(objs[0]["embedding"], dtype=np.float32)
    n = np.linalg.norm(v)
    if n < 1e-8:
        return None
    return (v / n).tolist()


def main():
    if not os.path.isdir(ENROLL_DIR):
        raise SystemExit(f"Klasör yok: {ENROLL_DIR}")

    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)
        print("Eski DB silindi.")

    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.create_collection(name="faces",
                                   metadata={"hnsw:space": "cosine"})

    files = sorted(f for f in os.listdir(ENROLL_DIR)
                   if f.lower().endswith((".png", ".jpg", ".jpeg")))
    print(f"{len(files)} fotoğraf bulundu, işleniyor...")

    embs, ids, skipped = [], [], []
    for i, f in enumerate(files, 1):
        v = get_embedding(os.path.join(ENROLL_DIR, f))
        if v is None:
            skipped.append(f)
            print(f"  [{i}/{len(files)}] {f}  -> SKIP (yüz bulunamadı)")
            continue
        embs.append(v)
        ids.append(f"Doga_{f}")
        print(f"  [{i}/{len(files)}] {f}  -> OK")

    if not embs:
        print("HATA: Hiç embedding üretilemedi.")
        return

    col.add(documents=["Doga"] * len(embs), embeddings=embs, ids=ids)
    print(f"\n=== TAMAMLANDI ===")
    print(f"Enroll edilen: {len(embs)} / {len(files)}")
    print(f"Atlanan:       {len(skipped)}")
    if skipped:
        print(f"\nAtlanan fotoğraflar (yüz tespiti başarısız):")
        for f in skipped:
            print(f"  - {f}")
        print("\nBu fotoğraflar büyük ihtimalle ya çok bulanık ya da yüz çok küçük.")
        print("Test setinden çıkarman önerilir; aksi halde haksız yere FRR'yi şişirirler.")


if __name__ == "__main__":
    main()