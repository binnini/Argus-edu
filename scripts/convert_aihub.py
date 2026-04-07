"""
convert_aihub.py — AI-HUB 수학 데이터를 Argus problems 스키마로 변환.

사용법:
    python scripts/convert_aihub.py

출력:
    data/problems/aihub_전과정_수학.json  — Argus 채점 문제 DB (초·중·고 전체)
    data/ocr_samples/labels.json         — OCR 파인튜닝 데이터 (초·중·고 전체)
"""

import json
import re
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LABEL_DIR = DATA_DIR / "AI_HUB" / "3.개방데이터" / "1.데이터" / "Training" / "02.라벨링데이터"

OUTPUT_FILE = DATA_DIR / "problems" / "aihub_전과정_수학.json"
OCR_LABELS_FILE = DATA_DIR / "ocr_samples" / "labels.json"

# 초·중·고 전체 학년 TL_1/TL_2/TL_3 세트
GRADE_SETS = [
    {
        "tl1": LABEL_DIR / "TL_1.문제_초등학교_3학년.zip",
        "tl2": LABEL_DIR / "TL_2.모범답안_초등학교_3학년.zip",
        "tl3": LABEL_DIR / "TL_3.손글씨풀이_초등학교_3학년.zip",
        "source": "AI-HUB_초등학교_3학년",
    },
    {
        "tl1": LABEL_DIR / "TL_1.문제_초등학교_4학년.zip",
        "tl2": LABEL_DIR / "TL_2.모범답안_초등학교_4학년.zip",
        "tl3": LABEL_DIR / "TL_3.손글씨풀이_초등학교_4학년.zip",
        "source": "AI-HUB_초등학교_4학년",
    },
    {
        "tl1": LABEL_DIR / "TL_1.문제_초등학교_5학년.zip",
        "tl2": LABEL_DIR / "TL_2.모범답안_초등학교_5학년.zip",
        "tl3": LABEL_DIR / "TL_3.손글씨풀이_초등학교_5학년.zip",
        "source": "AI-HUB_초등학교_5학년",
    },
    {
        "tl1": LABEL_DIR / "TL_1.문제_초등학교_6학년.zip",
        "tl2": LABEL_DIR / "TL_2.모범답안_초등학교_6학년.zip",
        "tl3": LABEL_DIR / "TL_3.손글씨풀이_초등학교_6학년.zip",
        "source": "AI-HUB_초등학교_6학년",
    },
    {
        "tl1": LABEL_DIR / "TL_1.문제_중학교_1학년.zip",
        "tl2": LABEL_DIR / "TL_2.모범답안_중학교_1학년.zip",
        "tl3": LABEL_DIR / "TL_3.손글씨풀이_중학교_1학년.zip",
        "source": "AI-HUB_중학교_1학년",
    },
    {
        "tl1": LABEL_DIR / "TL_1.문제_중학교_2학년.zip",
        "tl2": LABEL_DIR / "TL_2.모범답안_중학교_2학년.zip",
        "tl3": LABEL_DIR / "TL_3.손글씨풀이_중학교_2학년.zip",
        "source": "AI-HUB_중학교_2학년",
    },
    {
        "tl1": LABEL_DIR / "TL_1.문제_중학교_3학년.zip",
        "tl2": LABEL_DIR / "TL_2.모범답안_중학교_3학년.zip",
        "tl3": LABEL_DIR / "TL_3.손글씨풀이_중학교_3학년.zip",
        "source": "AI-HUB_중학교_3학년",
    },
    {
        "tl1": LABEL_DIR / "TL_1.문제_고등학교_공통수학.zip",
        "tl2": LABEL_DIR / "TL_2.모범답안_고등학교_공통수학.zip",
        "tl3": LABEL_DIR / "TL_3.손글씨풀이_고등학교_공통수학.zip",
        "source": "AI-HUB_고등학교_공통수학",
    },
]


def extract_answer(answer_bbox: list, answer_text: str) -> str | None:
    """answer_bbox에서 type=='answer'인 text를 추출. 없으면 answer_text 마지막 $...$ 항목."""
    for item in answer_bbox:
        if item.get("type") == "answer" and item.get("text"):
            return item["text"].strip()

    # fallback: answer_text의 마지막 $...$ 토큰
    tokens = re.findall(r"\$[^$]+\$", answer_text)
    if tokens:
        return tokens[-1].strip()

    return None


def build_reference_solution(answer_text: str, clac_bbox: list) -> dict:
    """answer_text와 clac_bbox로 reference_solution 단계 구조 생성."""
    # 98856 구분자로 단계 분리
    if "98856" in answer_text:
        raw_steps = [s.strip() for s in answer_text.split("98856") if s.strip()]
    else:
        # 구분자 없으면 전체를 1단계로
        raw_steps = [answer_text.strip()] if answer_text.strip() else []

    steps = []
    for i, content in enumerate(raw_steps):
        title = ""
        if i < len(clac_bbox):
            title = clac_bbox[i].get("name", "")
        steps.append({"step": i + 1, "title": title, "content": content})

    return {"steps": steps}


def build_rubric(required_num: int, clac_bbox: list) -> dict:
    """rubric 자동 생성."""
    total = required_num if required_num and required_num > 0 else 1
    steps = []
    for i in range(total):
        desc = clac_bbox[i].get("name", "") if i < len(clac_bbox) else ""
        steps.append({"step": i + 1, "description": desc, "score": 1})
    return {"total_score": total, "steps": steps}


def load_tl2_index(zf2: zipfile.ZipFile) -> dict[str, str]:
    """TL_2 zip 파일명 → zipfile 내부 경로 인덱스 생성."""
    index = {}
    for name in zf2.namelist():
        if name.endswith(".json"):
            index[Path(name).name] = name
    return index


def convert_grade(tl1_zip: Path, tl2_zip: Path, source: str) -> tuple[list, int, dict]:
    """단일 학년 TL_1+TL_2 zip에서 problems 목록 변환."""
    if not tl1_zip.exists():
        print(f"[WARN] TL_1 없음 (스킵): {tl1_zip.name}")
        return [], 0, {}
    if not tl2_zip.exists():
        print(f"[WARN] TL_2 없음 (스킵): {tl2_zip.name}")
        return [], 0, {}

    print(f"[INFO] 변환 중: {tl1_zip.name}")
    zf1 = zipfile.ZipFile(tl1_zip)
    zf2 = zipfile.ZipFile(tl2_zip)

    t1_names = [n for n in zf1.namelist() if n.endswith(".json")]
    tl2_index = load_tl2_index(zf2)
    print(f"  TL_1 파일 수: {len(t1_names)}")

    problems = []
    skipped = 0
    skip_reasons: dict[str, int] = {}

    for t1_path in t1_names:
        try:
            t1_data = json.loads(zf1.read(t1_path).decode("utf-8-sig"))
        except Exception as e:
            print(f"  [WARN] TL_1 읽기 실패: {t1_path} — {e}")
            skipped += 1
            skip_reasons["read_error"] = skip_reasons.get("read_error", 0) + 1
            continue

        q_info = t1_data.get("question_info", [{}])[0]

        # 서술 문제 필터링
        if q_info.get("question_type1") != "서술":
            skipped += 1
            skip_reasons["not_서술"] = skip_reasons.get("not_서술", 0) + 1
            continue

        pid = t1_data.get("id", "")
        question_text = t1_data.get("OCR_info", [{}])[0].get("question_text", "").strip()
        if not question_text:
            skipped += 1
            skip_reasons["no_question_text"] = skip_reasons.get("no_question_text", 0) + 1
            continue

        # TL_2 매핑
        t1_filename = Path(t1_path).stem
        t2_filename = t1_filename + "_A.json"
        t2_path = tl2_index.get(t2_filename)
        if not t2_path:
            skipped += 1
            skip_reasons["no_tl2"] = skip_reasons.get("no_tl2", 0) + 1
            continue

        try:
            t2_data = json.loads(zf2.read(t2_path).decode("utf-8-sig"))
        except Exception as e:
            print(f"  [WARN] TL_2 읽기 실패: {t2_path} — {e}")
            skipped += 1
            skip_reasons["tl2_read_error"] = skip_reasons.get("tl2_read_error", 0) + 1
            continue

        a_info = t2_data.get("answer_info", [{}])[0]
        answer_bbox = a_info.get("answer_bbox", [])
        answer_text = a_info.get("answer_text", "").strip()
        clac_bbox = a_info.get("answer_clac_bbox", [])
        required_num = a_info.get("answer_required_num") or 1

        answer = extract_answer(answer_bbox, answer_text)
        if not answer:
            skipped += 1
            skip_reasons["no_answer"] = skip_reasons.get("no_answer", 0) + 1
            continue

        reference_solution = build_reference_solution(answer_text, clac_bbox)
        rubric = build_rubric(required_num, clac_bbox)

        difficulty = q_info.get("question_difficulty")
        try:
            difficulty = int(difficulty)
            if not 1 <= difficulty <= 5:
                difficulty = 3
        except (TypeError, ValueError):
            difficulty = 3

        domain = q_info.get("question_topic_name") or source.replace("AI-HUB_", "")

        problems.append(
            {
                "id": pid,
                "title": pid,
                "content": question_text,
                "answer": answer,
                "reference_solution": reference_solution,
                "rubric": rubric,
                "domain": domain,
                "difficulty": difficulty,
                "source": source,
            }
        )

    zf1.close()
    zf2.close()
    print(f"  → {len(problems)}개 변환, {skipped}개 스킵 {skip_reasons}")
    return problems, skipped, skip_reasons


def convert() -> None:
    all_problems = []
    total_skipped = 0

    for grade in GRADE_SETS:
        problems, skipped, _ = convert_grade(grade["tl1"], grade["tl2"], grade["source"])
        all_problems.extend(problems)
        total_skipped += skipped

    print(f"\n[INFO] 전체 변환 완료: {len(all_problems)}개 문제 (스킵 {total_skipped}개)")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_problems, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 저장: {OUTPUT_FILE}")

    if all_problems:
        print("\n[SAMPLE] 첫 번째 문제:")
        print(json.dumps(all_problems[0], ensure_ascii=False, indent=2))

    # TL_3 → OCR labels.json (전 학년)
    convert_ocr_labels()


def convert_ocr_labels() -> None:
    """전 학년 TL_3 손글씨 풀이로 ocr_samples/labels.json 생성.

    OCR 파인튜닝용 데이터이므로 problem_id 필터링 없이 전체 수집.
    문제 난이도와 무관하게 손글씨 이미지 + ground truth 텍스트만 필요.
    """
    labels = []
    total_skipped = 0

    for grade in GRADE_SETS:
        tl3_zip = grade["tl3"]
        source = grade["source"]
        if not tl3_zip.exists():
            print(f"[WARN] TL_3 없음 (스킵): {tl3_zip.name}")
            continue

        print(f"[INFO] TL_3 로드 중: {tl3_zip.name}")
        zf3 = zipfile.ZipFile(tl3_zip)
        skipped = 0
        count_before = len(labels)

        for t3_path in zf3.namelist():
            if not t3_path.endswith(".json"):
                continue

            try:
                t3_data = json.loads(zf3.read(t3_path).decode("utf-8-sig"))
            except Exception as e:
                print(f"[WARN] TL_3 읽기 실패: {t3_path} — {e}")
                skipped += 1
                continue

            e_info = t3_data.get("explanation_info", [{}])[0]
            filename = e_info.get("explanation_filename") or ""
            text = (e_info.get("explanation_text") or "").strip()
            correct = e_info.get("explanation_correct", 0)

            if not filename or not text:
                skipped += 1
                continue

            labels.append(
                {
                    "image": f"images/{filename}",
                    "ground_truth_text": text,
                    "expected_result": "correct" if correct == 1 else "wrong",
                    "source": source,
                }
            )

        zf3.close()
        added = len(labels) - count_before
        total_skipped += skipped
        print(f"  → {added}개 추가 (스킵 {skipped}개)")

    OCR_LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OCR_LABELS_FILE, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    print(f"\n[INFO] OCR labels 저장: {OCR_LABELS_FILE}")
    print(f"[INFO] 전체 {len(labels)}개 (전체 스킵 {total_skipped}개)")


if __name__ == "__main__":
    convert()
