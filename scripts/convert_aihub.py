"""
convert_aihub.py — AI-HUB 수학 데이터를 Argus problems 스키마로 변환.

사용법:
    python scripts/convert_aihub.py

출력:
    data/problems/aihub_고등학교_공통수학.json
    data/ocr_samples/labels.json
"""

import json
import re
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LABEL_DIR = DATA_DIR / "AI_HUB" / "3.개방데이터" / "1.데이터" / "Training" / "02.라벨링데이터"

TL1_ZIP = LABEL_DIR / "TL_1.문제_고등학교_공통수학.zip"
TL2_ZIP = LABEL_DIR / "TL_2.모범답안_고등학교_공통수학.zip"
TL3_ZIP = LABEL_DIR / "TL_3.손글씨풀이_고등학교_공통수학.zip"

OUTPUT_FILE = DATA_DIR / "problems" / "aihub_고등학교_공통수학.json"
OCR_LABELS_FILE = DATA_DIR / "ocr_samples" / "labels.json"

SOURCE = "AI-HUB_고등학교_공통수학"


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


def convert() -> None:
    print(f"[INFO] TL_1 로드 중: {TL1_ZIP.name}")
    print(f"[INFO] TL_2 로드 중: {TL2_ZIP.name}")

    zf1 = zipfile.ZipFile(TL1_ZIP)
    zf2 = zipfile.ZipFile(TL2_ZIP)

    t1_names = [n for n in zf1.namelist() if n.endswith(".json")]
    tl2_index = load_tl2_index(zf2)

    print(f"[INFO] TL_1 문제 수: {len(t1_names)}")

    problems = []
    skipped = 0
    skip_reasons: dict[str, int] = {}

    for t1_path in t1_names:
        try:
            t1_data = json.loads(zf1.read(t1_path).decode("utf-8-sig"))
        except Exception as e:
            print(f"[WARN] TL_1 읽기 실패: {t1_path} — {e}")
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
        t1_filename = Path(t1_path).stem  # e.g. H_1_01_25766_84187
        t2_filename = t1_filename + "_A.json"
        t2_path = tl2_index.get(t2_filename)
        if not t2_path:
            print(f"[WARN] TL_2 없음: {t2_filename}")
            skipped += 1
            skip_reasons["no_tl2"] = skip_reasons.get("no_tl2", 0) + 1
            continue

        try:
            t2_data = json.loads(zf2.read(t2_path).decode("utf-8-sig"))
        except Exception as e:
            print(f"[WARN] TL_2 읽기 실패: {t2_path} — {e}")
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
            print(f"[WARN] answer 추출 실패, 스킵: {pid}")
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

        domain = q_info.get("question_topic_name") or "고등학교_공통수학"

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
                "source": SOURCE,
            }
        )

    zf1.close()
    zf2.close()

    print(f"\n[INFO] 변환 완료: {len(problems)}개 문제")
    print(f"[INFO] 스킵: {skipped}개 — {skip_reasons}")

    # 출력 저장
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 저장: {OUTPUT_FILE}")

    # 샘플 1개 출력
    if problems:
        print("\n[SAMPLE] 첫 번째 문제:")
        print(json.dumps(problems[0], ensure_ascii=False, indent=2))

    # TL_3 → OCR labels.json
    convert_ocr_labels(problems)


def convert_ocr_labels(problems: list) -> None:
    """TL_3 손글씨 풀이로 ocr_samples/labels.json 생성."""
    print(f"\n[INFO] TL_3 로드 중: {TL3_ZIP.name}")
    zf3 = zipfile.ZipFile(TL3_ZIP)

    # problem id → DB 삽입 후 id를 모르므로 title(=pid) 기준으로 매핑
    pid_set = {p["id"] for p in problems}

    labels = []
    skipped = 0

    for t3_path in zf3.namelist():
        if not t3_path.endswith(".json"):
            continue

        try:
            t3_data = json.loads(zf3.read(t3_path).decode("utf-8-sig"))
        except Exception as e:
            print(f"[WARN] TL_3 읽기 실패: {t3_path} — {e}")
            skipped += 1
            continue

        pid = t3_data.get("id", "")
        if pid not in pid_set:
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
                "problem_id": pid,  # DB 삽입 후 실제 int id로 교체 필요
                "ground_truth_text": text,
                "expected_result": "correct" if correct == 1 else "wrong",
            }
        )

    zf3.close()

    OCR_LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OCR_LABELS_FILE, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)
    print(f"[INFO] OCR labels 저장: {OCR_LABELS_FILE} ({len(labels)}개, 스킵 {skipped}개)")


if __name__ == "__main__":
    convert()
