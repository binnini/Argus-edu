"""
Step 1: TS_3 zip 8개 + 038 손글씨 zip 9개 → data/ocr_samples/images/ 추출
"""
import zipfile
from pathlib import Path
from tqdm import tqdm
import json

BASE = Path.home() / "projects/Argus-edu"
AI_HUB = BASE / "data/AI_HUB"
OUT_DIR = BASE / "data/ocr_samples/images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# TS_3 손글씨 풀이 zip (기존)
TS3_DIR = AI_HUB / "3.개방데이터/1.데이터/Training/01.원천데이터"
TS3_ZIPS = [
    TS3_DIR / "TS_3.손글씨풀이_초등학교_3학년.zip",
    TS3_DIR / "TS_3.손글씨풀이_초등학교_4학년.zip",
    TS3_DIR / "TS_3.손글씨풀이_초등학교_5학년.zip",
    TS3_DIR / "TS_3.손글씨풀이_초등학교_6학년.zip",
    TS3_DIR / "TS_3.손글씨풀이_중학교_1학년.zip",
    TS3_DIR / "TS_3.손글씨풀이_중학교_2학년.zip",
    TS3_DIR / "TS_3.손글씨풀이_중학교_3학년.zip",
    TS3_DIR / "TS_3.손글씨풀이_고등학교_공통수학.zip",
]

# 038 손글씨 zip (추가)
OCR038_DIR = AI_HUB / "038.수식, 도형, 낙서기호 OCR 데이터/01.데이터/1.Training/원천데이터"
OCR038_ZIPS = [
    OCR038_DIR / "TS_손초4.zip",
    OCR038_DIR / "TS_손초5.zip",
    OCR038_DIR / "TS_손초6.zip",
    OCR038_DIR / "TS_손중1.zip",
    OCR038_DIR / "TS_손중2.zip",
    OCR038_DIR / "TS_손중3.zip",
    OCR038_DIR / "TS_손고1.zip",
    OCR038_DIR / "TS_손고2.zip",
    OCR038_DIR / "TS_손고3.zip",
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def extract_zip(zip_path: Path, out_dir: Path) -> int:
    extracted = 0
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.infolist() if Path(m.filename).suffix.lower() in IMAGE_EXTS]
        for member in tqdm(members, desc=zip_path.name, leave=False):
            dest = out_dir / Path(member.filename).name
            if dest.exists():
                continue
            with zf.open(member) as src, open(dest, "wb") as dst:
                dst.write(src.read())
            extracted += 1
    return extracted


def main():
    total = 0
    all_zips = [(z, "TS3") for z in TS3_ZIPS] + [(z, "038") for z in OCR038_ZIPS]

    for zip_path, tag in all_zips:
        if not zip_path.exists():
            print(f"[SKIP] 없음: {zip_path}")
            continue
        n = extract_zip(zip_path, OUT_DIR)
        total += n
        print(f"[{tag}] {zip_path.name}: {n:,}개 추출")

    # labels.json 첫 10개 이미지 존재 검증
    labels_path = BASE / "data/ocr_samples/labels.json"
    if labels_path.exists():
        with open(labels_path) as f:
            labels = json.load(f)
        ok = sum(1 for item in labels[:10] if (OUT_DIR / Path(item["image"]).name).exists())
        print(f"\nlabels.json 검증: 첫 10개 중 {ok}개 이미지 존재")

    img_count = sum(1 for p in OUT_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    print(f"\n이미지 추출 완료: {total:,}개 신규 / 디렉토리 합계: {img_count:,}개")


if __name__ == "__main__":
    main()
