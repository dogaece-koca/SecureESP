import argparse
import hashlib
import hmac
import os
import statistics
import sys
import time

import requests


SECRET_KEY = b"Doga_Project_Secret_Key_2026"


def hmac_sign(data: bytes) -> str:
    return hmac.new(SECRET_KEY, data, hashlib.sha256).hexdigest()


def one_trial(url: str, image_bytes: bytes) -> tuple[float, float, float, int, str]:
    """Tek bir deneme yapar, (toplam_ms, hmac_ms, network_ms, status, response) döner."""
    t0 = time.perf_counter()
    sig = hmac_sign(image_bytes)
    t1 = time.perf_counter()
    try:
        r = requests.post(
            url,
            data=image_bytes,
            headers={"X-Signature": sig, "Content-Type": "application/octet-stream"},
            timeout=30,
        )
        body = r.text
        status = r.status_code
    except requests.exceptions.RequestException as e:
        return (0.0, 0.0, 0.0, 0, f"HATA: {e}")
    t2 = time.perf_counter()

    return (
        (t2 - t0) * 1000.0,   # toplam ms
        (t1 - t0) * 1000.0,   # hmac süresi
        (t2 - t1) * 1000.0,   # network + sunucu işleme
        status,
        body.strip(),
    )


def stats(label, samples):
    if not samples:
        print(f"{label}: veri yok")
        return
    s = sorted(samples)
    n = len(s)
    p50 = s[n // 2]
    p95 = s[int(0.95 * (n - 1))]
    mean = statistics.mean(s)
    stdev = statistics.stdev(s) if n > 1 else 0.0
    print(f"  {label:<22} ortalama={mean:7.1f} ms   medyan={p50:7.1f} ms   "
          f"p95={p95:7.1f} ms   std={stdev:6.1f} ms   "
          f"min={s[0]:.1f}   max={s[-1]:.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30, help="Deneme sayısı")
    ap.add_argument("--url", default="http://127.0.0.1:8080/upload")
    ap.add_argument("--photo", default=None,
                    help="Test fotoğrafı (varsayılan: test_doga klasöründen ilk dosya)")
    ap.add_argument("--warmup", type=int, default=3,
                    help="Isınma denemesi (istatistiğe dahil edilmez)")
    args = ap.parse_args()

    # Test fotoğrafını bul
    if args.photo:
        photo = args.photo
    else:
        for cand in ("test_doga", "test/test_doga"):
            if os.path.isdir(cand):
                files = sorted(f for f in os.listdir(cand)
                               if f.lower().endswith((".jpg", ".jpeg", ".png")))
                if files:
                    photo = os.path.join(cand, files[0])
                    break
        else:
            print("HATA: --photo ile bir test fotoğrafı belirt.")
            sys.exit(1)

    if not os.path.exists(photo):
        print(f"HATA: dosya yok: {photo}")
        sys.exit(1)

    with open(photo, "rb") as f:
        image_bytes = f.read()

    payload_kb = len(image_bytes) / 1024
    print(f"Sunucu:        {args.url}")
    print(f"Fotoğraf:      {photo}  ({payload_kb:.1f} KB)")
    print(f"Isınma:        {args.warmup} deneme (istatistiğe dahil değil)")
    print(f"Ölçüm:         {args.n} deneme")
    print("=" * 80)

    # Isınma (ilk istekler genelde Python/Flask cache ısınmasından yavaş olur)
    print("Isınma...")
    for i in range(args.warmup):
        total, _, _, status, _ = one_trial(args.url, image_bytes)
        print(f"  [warmup {i+1}/{args.warmup}] {total:6.1f} ms  status={status}")

    print("\nÖlçüm başlıyor...")
    totals, hmacs, nets = [], [], []
    granted = denied = errored = 0
    for i in range(args.n):
        total, hsec, nsec, status, body = one_trial(args.url, image_bytes)
        if status == 0:
            errored += 1
            print(f"  [{i+1:3d}/{args.n}] HATA")
            continue
        if "GRANTED" in body:
            granted += 1
        else:
            denied += 1
        totals.append(total)
        hmacs.append(hsec)
        nets.append(nsec)
        print(f"  [{i+1:3d}/{args.n}] toplam={total:6.1f} ms   "
              f"hmac={hsec:5.2f} ms   network+server={nsec:6.1f} ms   "
              f"status={status}")

    print("\n" + "=" * 80)
    print("ÖZET")
    print("=" * 80)
    print(f"Başarılı: {len(totals)} / {args.n}   (granted={granted}  denied={denied}"
          f"  errored={errored})\n")
    stats("Uçtan-uca toplam", totals)
    stats("HMAC-SHA256",       hmacs)
    stats("Network + Server",  nets)

    if totals:
        print("\nPaper için tek satır:")
        print(f"  Ortalama uçtan-uca gecikme: {statistics.mean(totals)/1000:.2f} s   "
              f"(n={len(totals)}, p95={sorted(totals)[int(0.95*(len(totals)-1))]/1000:.2f} s)")


if __name__ == "__main__":
    main()