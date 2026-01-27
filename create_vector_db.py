import os
import chromadb
from deepface import DeepFace

DB_PATH = "my_face_db"

# Fotoğrafların bulunduğu ana klasör
# Yapısı şöyle olmalı: dataset_cropped/doga, dataset_cropped/others
DATASET_PATH = "dataset_cropped"

MODEL_NAME = "Facenet512"

def create_database():

    if not os.path.exists(DATASET_PATH):
        print(f"ERROR: '{DATASET_PATH}' not found")
        return

    print(f"Database is getting started: {DB_PATH}...")
    client = chromadb.PersistentClient(path=DB_PATH)

    try:
        client.delete_collection(name="faces")
        print("Old Database is cleaned. Starting over.")
    except:
        pass

    collection = client.create_collection(name="faces")


    total_processed = 0
    total_errors = 0

    for person_name in os.listdir(DATASET_PATH):
        person_folder = os.path.join(DATASET_PATH, person_name)

        if not os.path.isdir(person_folder): continue

        print(f"\n Processing: {person_name}...")


        for filename in os.listdir(person_folder):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')): continue

            img_path = os.path.join(person_folder, filename)

            try:

                embedding_objs = DeepFace.represent(
                    img_path=img_path,
                    model_name=MODEL_NAME,
                    enforce_detection=False
                )


                embedding = embedding_objs[0]["embedding"]


                collection.add(
                    documents=[person_name],
                    metadatas=[{"filename": filename}],
                    ids=[f"{person_name}_{filename}"],
                    embeddings=[embedding]
                )

                print(f"  Added: {filename}")
                total_processed += 1

            except Exception as e:
                print(f"   Error ({filename}): {e}")
                total_errors += 1

    print("\n" + "=" * 40)
    print(f"Process Completed")
    print(f"Successfully: {total_processed}")
    print(f"Total Errors: {total_errors}")
    print(f"Database Location: {os.path.abspath(DB_PATH)}")
    print("=" * 40)

if __name__ == "__main__":
    create_database()