import os
import urllib.request

SAVE_DIR = r"C:\Users\JW\Desktop\왜가리"

# 0x0으로 감지된 lazy-load 이미지들
lazy_imgs = [
    "https://k.kakaocdn.net/dn/7FGIs/dJMcacwzrIC/AbjJ7A4eBpO0atKi8ptWa1/img.png",
    "https://k.kakaocdn.net/dn/cGVqE4/dJMcabxBDZ3/9vMImawcoZnGlthzqX1ae1/img.png",
    "https://k.kakaocdn.net/dn/dbPtNG/dJMcai4uV6a/v06YfnDMaE2J5AA0PTKfvK/img.png",
    "https://k.kakaocdn.net/dn/ngxvr/dJMcabYGZMP/PfMSPuc3UjaeJyljPPUio1/img.png",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://pf.kakao.com/",
}

existing = len([f for f in os.listdir(SAVE_DIR) if f.endswith(('.png','.jpg','.gif','.webp'))])
print(f"기존 파일 수: {existing}")

for idx, url in enumerate(lazy_imgs, existing + 1):
    filepath = os.path.join(SAVE_DIR, f"{idx:03d}.png")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) > 1000:
            with open(filepath, "wb") as f:
                f.write(data)
            print(f"[{idx}] 저장: {filepath} ({len(data)} bytes)")
        else:
            print(f"[{idx}] 너무 작음 ({len(data)} bytes), 건너뜀")
    except Exception as e:
        print(f"[{idx}] 실패: {e}")

total = len([f for f in os.listdir(SAVE_DIR) if f.endswith(('.png','.jpg','.gif','.webp'))])
print(f"\n최종 저장 파일 수: {total}개 → {SAVE_DIR}")
