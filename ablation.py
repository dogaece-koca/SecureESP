
import os
import sys
import csv
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from deepface import DeepFace

ENROLL_DIR = r"C:\Users\doaec\PycharmProjects\ESPSecure\dataset_cropped\doga"
TEST_DOGA_DIR = r"C:\Users\doaec\PycharmProjects\ESPSecure\test\test_doga"
TEST_YABANCI_DIR = r"C:\Users\doaec\PycharmProjects\ESPSecure\test\test_yabanci"

DETECTOR = "retinaface"
MODELS = ["SFace", "ArcFace", "Facenet512"]
TOP_K = 5


THR_RANGES = {
    "SFace":      (0.30, 0.85, 56),
    "ArcFace":    (0.30, 0.95, 66),
    "Facenet512": (0.10, 0.70, 61),
}


def list_imgs(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(os.path.join(folder, f) for f in os.listdir(folder)
                  if f.lower().endswith((".png", ".jpg", ".jpeg")))


def embed(path, model_name):
    try:
        objs = DeepFace.represent(
            img_path=path, model_name=model_name,
            detector_backend=DETECTOR, enforce_detection=True, align=True,
        )
    except Exception:
        return None
    if not objs:
        return None
    v = np.array(objs[0]["embedding"], dtype=np.float32)
    n = np.linalg.norm(v)
    return None if n < 1e-8 else v / n


def collect(paths, model_name, label):
    out, skipped = [], []
    for i, p in enumerate(paths, 1):
        v = embed(p, model_name)
        if v is None:
            skipped.append(os.path.basename(p))
        else:
            out.append((os.path.basename(p), v))
        if i % 10 == 0 or i == len(paths):
            print(f"  {label}: {i}/{len(paths)} (skipped={len(skipped)})")
    return out, skipped


def cos_dist_matrix(query_embs, db_embs):
    Q = np.stack([v for _, v in query_embs])
    D = np.stack([v for _, v in db_embs])
    return 1.0 - Q @ D.T


def score_min_topk(dist_row, k):
    idx = np.argpartition(dist_row, k - 1)[:k]
    return float(np.min(dist_row[idx]))


def evaluate_model(model_name):
    print(f"\n=== {model_name} ===")
    print("Enrollment...")
    enroll, _ = collect(list_imgs(ENROLL_DIR), model_name, "enroll")
    if not enroll:
        return None
    print("Test (Doga)...")
    g_set, _ = collect(list_imgs(TEST_DOGA_DIR), model_name, "doga")
    print("Test (Yabancı)...")
    i_set, _ = collect(list_imgs(TEST_YABANCI_DIR), model_name, "yab")

    if not g_set or not i_set:
        return None

    g_d = cos_dist_matrix(g_set, enroll)
    i_d = cos_dist_matrix(i_set, enroll)
    k = min(TOP_K, len(enroll))
    g_scores = np.array([score_min_topk(g_d[r], k) for r in range(g_d.shape[0])])
    i_scores = np.array([score_min_topk(i_d[r], k) for r in range(i_d.shape[0])])


    with open(f"ablation_{model_name}_scores.csv", "w", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["filename", "true_class", "score"])
        for (fn, _), s in zip(g_set, g_scores):
            w.writerow([fn, "Doga", f"{s:.6f}"])
        for (fn, _), s in zip(i_set, i_scores):
            w.writerow([fn, "Yabanci", f"{s:.6f}"])

    lo, hi, n = THR_RANGES[model_name]
    ts = np.linspace(lo, hi, n)
    rows = []
    for t in ts:
        frr = float(np.mean(g_scores >= t))
        far = float(np.mean(i_scores < t))
        rows.append((t, frr, far))

    diffs = [abs(frr - far) for _, frr, far in rows]
    eer_idx = int(np.argmin(diffs))
    t_eer, frr_eer, far_eer = rows[eer_idx]
    eer = (frr_eer + far_eer) / 2

    feas = [(t, frr, far) for t, frr, far in rows if far <= 0.05]
    if feas:
        feas.sort(key=lambda x: (x[1], -x[0]))
        t_op, frr_op, far_op = feas[0]
    else:
        t_op, frr_op, far_op = t_eer, frr_eer, far_eer

    return {
        "model": model_name,
        "n_enroll": len(enroll),
        "n_test_doga": len(g_set),
        "n_test_yab": len(i_set),
        "g_scores": g_scores,
        "i_scores": i_scores,
        "t_eer": t_eer, "eer": eer,
        "t_op": t_op, "frr_op": frr_op, "far_op": far_op,
        "rows": rows,
    }


def main():
    results = []
    for m in MODELS:
        r = evaluate_model(m)
        if r is not None:
            results.append(r)

    if not results:
        print("Hiçbir model değerlendirilemedi.")
        return

    # Markdown tablosu
    md = []
    md.append("# Backbone Ablation Results\n")
    md.append(f"Detector: `{DETECTOR}` | Decision: `min(top-{TOP_K})` | "
              f"Enroll: {results[0]['n_enroll']} images | "
              f"Test: {results[0]['n_test_doga']} Doga + {results[0]['n_test_yab']} Impostor\n")
    md.append("| Model | EER (%) | t_EER | t for FAR≤5% | FRR (%) | FAR (%) |")
    md.append("|---|---|---|---|---|---|")
    for r in results:
        md.append(f"| **{r['model']}** | {r['eer'] * 100:.1f} | {r['t_eer']:.3f} | "
                  f"{r['t_op']:.3f} | {r['frr_op'] * 100:.1f} | {r['far_op'] * 100:.1f} |")

    md.append("\n## Score Distributions (Summary)\n")
    md.append("| Model | Doga med | Impostor med | Separation |")
    md.append("|---|---|---|---|")
    for r in results:
        gm = float(np.median(r["g_scores"]))
        im = float(np.median(r["i_scores"]))
        md.append(f"| {r['model']} | {gm:.3f} | {im:.3f} | {im - gm:+.3f} |")

    md_text = "\n".join(md) + "\n"
    with open("ablation_results.md", "w", encoding="utf-8") as f:
        f.write(md_text)

    print("\n" + "=" * 60)
    print(md_text)
    print("=" * 60)
    print("ablation_results.md ve ablation_<model>_scores.csv yazıldı.")

    # Karşılaştırmalı ROC plot (İngilizce)
    plt.figure(figsize=(7, 6))
    for r in results:
        far_arr = np.array([row[2] for row in r["rows"]])
        tpr_arr = 1 - np.array([row[1] for row in r["rows"]])
        plt.plot(far_arr, tpr_arr, marker=".", label=f"{r['model']} (EER={r['eer'] * 100:.1f}%)")
    plt.xlabel("FAR (False Acceptance Rate)")
    plt.ylabel("TPR (1 - FRR)")
    plt.title(f"ROC Comparison | det={DETECTOR}, min(top-{TOP_K})")
    plt.legend()
    plt.grid(True, alpha=.3)
    plt.savefig("ablation_roc.png", dpi=140, bbox_inches="tight")
    print("ablation_roc.png yazıldı.")


if __name__ == "__main__":
    main()
