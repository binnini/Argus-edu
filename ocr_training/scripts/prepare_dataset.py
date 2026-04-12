"""
Step 2: labels.json(TS_3) + 038 손글씨 JSON → GOT-OCR conversation JSONL
출력: data/ocr_samples/dataset/train.jsonl, test.jsonl
"""
import json
import random
import re
import zipfile
from pathlib import Path
from tqdm import tqdm

BASE = Path.home() / "projects/Argus-edu"
IMAGES_DIR = BASE / "data/ocr_samples/images"
DATASET_DIR = BASE / "data/ocr_samples/dataset"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

LABELS_JSON = BASE / "data/ocr_samples/labels.json"
OCR038_LABEL_DIR = (
    BASE / "data/AI_HUB/038.수식, 도형, 낙서기호 OCR 데이터"
    / "01.데이터/1.Training/라벨링데이터"
)
OCR038_LABEL_ZIPS = [
    OCR038_LABEL_DIR / "TL_손초4.zip",
    OCR038_LABEL_DIR / "TL_손초5.zip",
    OCR038_LABEL_DIR / "TL_손초6.zip",
    OCR038_LABEL_DIR / "TL_손중1.zip",
    OCR038_LABEL_DIR / "TL_손중2.zip",
    OCR038_LABEL_DIR / "TL_손중3.zip",
    OCR038_LABEL_DIR / "TL_손고1.zip",
    OCR038_LABEL_DIR / "TL_손고2.zip",
    OCR038_LABEL_DIR / "TL_손고3.zip",
]

DISPLAYSTYLE_RE = re.compile(r"\\displaystyle\s*")


def normalize_latex(text: str) -> str:
    """038 데이터의 \\displaystyle 제거해 TS_3 스타일과 통일"""
    return DISPLAYSTYLE_RE.sub("", text).strip()


def make_conversation(image_path: Path, ground_truth: str) -> dict:
    img_str = str(image_path)
    return {
        "id": image_path.stem,
        "image": img_str,
        "conversations": [
            {
                "from": "human",
                "value": f"<img>{img_str}</img>\nOCR with format: ",
            },
            {
                "from": "gpt",
                "value": ground_truth,
            },
        ],
    }


def load_ts3_records() -> list[dict]:
    """TS_3 labels.json → conversation 레코드 목록"""
    if not LABELS_JSON.exists():
        print(f"[WARN] {LABELS_JSON} 없음 — TS_3 스킵")
        return []

    with open(LABELS_JSON) as f:
        labels = json.load(f)

    records = []
    for item in tqdm(labels, desc="TS_3 labels.json"):
        gt = item.get("ground_truth_text", "").strip()
        if not gt:
            continue
        img_path = IMAGES_DIR / Path(item["image"]).name
        if not img_path.exists():
            continue
        records.append(make_conversation(img_path, gt))

    print(f"TS_3: {len(records):,}개 로드")
    return records


def load_038_records() -> list[dict]:
    """038 손글씨 라벨 zip → conversation 레코드 목록"""
    records = []

    for zip_path in OCR038_LABEL_ZIPS:
        if not zip_path.exists():
            print(f"[SKIP] 없음: {zip_path.name}")
            continue

        zip_records = []
        with zipfile.ZipFile(zip_path) as zf:
            json_names = [n for n in zf.namelist() if n.endswith(".json")]
            for name in tqdm(json_names, desc=zip_path.name, leave=False):
                with zf.open(name) as f:
                    data = json.load(f)

                # 수식/텍스트 segment만 수집
                equations = [
                    normalize_latex(seg["equation"])
                    for seg in data.get("segments", [])
                    if seg.get("type") == "수식/텍스트"
                    and seg.get("equation", "").strip()
                ]
                if not equations:
                    continue

                gt = "\n".join(equations)

                # 대응 이미지 파일명: JSON과 동일한 stem, 확장자는 .png/.jpg
                stem = Path(name).stem
                img_path = None
                for ext in (".png", ".jpg", ".jpeg"):
                    candidate = IMAGES_DIR / (stem + ext)
                    if candidate.exists():
                        img_path = candidate
                        break

                if img_path is None:
                    continue

                zip_records.append(make_conversation(img_path, gt))

        print(f"{zip_path.name}: {len(zip_records):,}개 로드")
        records.extend(zip_records)

    print(f"038 합계: {len(records):,}개 로드")
    return records


def main():
    records = load_ts3_records() + load_038_records()
    print(f"\n전체: {len(records):,}개")

    random.seed(42)
    random.shuffle(records)

    split = int(len(records) * 0.9)
    train, test = records[:split], records[split:]

    for name, data in [("train", train), ("test", test)]:
        path = DATASET_DIR / f"{name}.jsonl"
        with open(path, "w") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"train: {len(train):,}개, test: {len(test):,}개")
    print(f"저장 완료: {DATASET_DIR}")


if __name__ == "__main__":
    main()
