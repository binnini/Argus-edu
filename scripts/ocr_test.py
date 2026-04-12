#!/usr/bin/env python3
"""
ocr_test.py — GOT-OCR 2.0 결과 확인 실험 스크립트.

백엔드와 동일한 ocr_worker.py 서브프로세스를 사용하므로 실제 서비스 동작을 그대로 재현합니다.

사용법:
  # 업로드 폴더 전체 테스트 (정답 없음)
  python scripts/ocr_test.py --uploads

  # 특정 이미지 1장 테스트
  python scripts/ocr_test.py --image backend/uploads/abc123.png

  # 이미지 디렉터리 전체 테스트
  python scripts/ocr_test.py --dir backend/uploads/ --limit 10

  # labels.json 기반 정확도 측정 (--images-root 로 실제 이미지 경로 지정 필요)
  python scripts/ocr_test.py --labels data/ocr_samples/labels.json \\
      --images-root /path/to/images/ --sample 20

  # test.jsonl 기반 정확도 측정 (경로 리매핑 포함)
  python scripts/ocr_test.py --jsonl data/ocr_samples/dataset/test.jsonl \\
      --images-root /path/to/images/ --sample 20

  # 결과 CSV 저장
  python scripts/ocr_test.py --uploads --output results.csv
"""

import argparse
import base64
import csv
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

# ── 프로젝트 루트 기준 기본 경로 ───────────────────────────────────────
ROOT = Path(__file__).parent.parent
DEFAULT_MODEL_PATH = str(ROOT / "ocr_training/output/got_ocr_merged")
DEFAULT_WORKER_PYTHON = "/opt/homebrew/Caskroom/miniconda/base/envs/argus-gotocr/bin/python"
DEFAULT_WORKER_SCRIPT = str(ROOT / "backend/scripts/ocr_worker.py")
DEFAULT_UPLOADS_DIR = str(ROOT / "backend/uploads")


# ── CER 계산 ──────────────────────────────────────────────────────────

def cer(pred: str, ref: str) -> float:
    """Character Error Rate (Levenshtein / len(ref))."""
    if not ref:
        return 0.0
    # 순수 파이썬 Levenshtein (외부 패키지 없이)
    s1, s2 = pred, ref
    m, n = len(s1), len(s2)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n] / n


# ── OCR Worker 관리 ────────────────────────────────────────────────────

class OcrWorker:
    """백엔드와 동일한 ocr_worker.py 서브프로세스를 실행."""

    def __init__(self, model_path: str, worker_python: str, worker_script: str):
        self.model_path = model_path
        self.worker_python = worker_python
        self.worker_script = worker_script
        self._proc: subprocess.Popen | None = None

    def start(self, timeout: float = 120.0):
        print(f"  모델 로딩 중: {self.model_path}")
        print(f"  Python  환경: {self.worker_python}")
        self._proc = subprocess.Popen(
            [self.worker_python, self.worker_script, "--model-path", self.model_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # 'ready' 신호 대기
        start = time.time()
        while time.time() - start < timeout:
            line = self._proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            try:
                msg = json.loads(line.decode())
                if msg.get("ready"):
                    print("  GOT-OCR 워커 준비 완료\n")
                    return
                print(f"  워커 메시지: {msg}", file=sys.stderr)
            except json.JSONDecodeError:
                pass
        raise TimeoutError(f"GOT-OCR 워커 시작 타임아웃 ({timeout:.0f}s)")

    def recognize(self, image_path: str) -> tuple[str, float]:
        """이미지 파일 경로를 받아 OCR 결과와 소요 시간(초)을 반환."""
        image_bytes = Path(image_path).read_bytes()
        content_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        return self.recognize_bytes(image_bytes, content_type)

    def recognize_bytes(self, image_bytes: bytes, content_type: str = "image/jpeg") -> tuple[str, float]:
        req_id = uuid.uuid4().hex
        req = json.dumps({
            "id": req_id,
            "image_b64": base64.b64encode(image_bytes).decode(),
            "content_type": content_type,
        }, ensure_ascii=False) + "\n"

        t0 = time.time()
        self._proc.stdin.write(req.encode())
        self._proc.stdin.flush()
        resp_line = self._proc.stdout.readline()
        elapsed = time.time() - t0

        resp = json.loads(resp_line.decode())
        if "error" in resp:
            raise RuntimeError(resp["error"])
        return resp.get("text", ""), elapsed

    def stop(self):
        if self._proc:
            self._proc.stdin.close()
            self._proc.wait(timeout=5)


# ── 이미지 수집 ────────────────────────────────────────────────────────

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def collect_from_dir(dir_path: str, limit: int | None = None) -> list[dict]:
    """디렉터리에서 이미지 파일 목록 수집 (정답 없음)."""
    files = sorted(
        p for p in Path(dir_path).iterdir()
        if p.suffix.lower() in IMAGE_EXTS
    )
    if limit:
        files = files[:limit]
    return [{"image": str(f), "ground_truth": None} for f in files]


def collect_from_labels(
    labels_json: str,
    images_root: str | None,
    sample: int | None,
) -> list[dict]:
    """labels.json에서 샘플 수집."""
    with open(labels_json, encoding="utf-8") as f:
        records = json.load(f)
    if sample:
        random.shuffle(records)
        records = records[:sample]
    result = []
    for r in records:
        img = r.get("image", "")
        # 상대 경로면 labels.json 위치 기준으로 절대화
        if not os.path.isabs(img):
            base = images_root or str(Path(labels_json).parent)
            img = str(Path(base) / img)
        elif images_root:
            # 절대 경로라도 images_root로 리매핑
            img = str(Path(images_root) / Path(img).name)
        result.append({
            "image": img,
            "ground_truth": r.get("ground_truth_text"),
            "id": Path(img).stem,
        })
    return result


def collect_from_jsonl(
    jsonl_path: str,
    images_root: str | None,
    sample: int | None,
) -> list[dict]:
    """test.jsonl에서 샘플 수집. images_root로 경로 리매핑 가능."""
    with open(jsonl_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    if sample:
        random.seed(42)
        records = random.sample(records, min(sample, len(records)))
    result = []
    for r in records:
        img = r.get("image", "")
        if images_root:
            img = str(Path(images_root) / Path(img).name)
        gt = None
        convs = r.get("conversations", [])
        if len(convs) >= 2:
            gt = convs[1].get("value", "")
        result.append({
            "image": img,
            "ground_truth": gt,
            "id": r.get("id", Path(img).stem),
        })
    return result


# ── 출력 헬퍼 ─────────────────────────────────────────────────────────

def truncate(s: str, width: int) -> str:
    s = s.replace("\n", "\\n")
    return s if len(s) <= width else s[:width - 1] + "…"


def print_header():
    print(f"{'#':>4}  {'파일명':<30}  {'소요':>6}  {'CER':>6}  {'예측 결과'}")
    print("-" * 100)


def print_row(idx: int, name: str, elapsed: float, cer_val: float | None, pred: str, error: str | None):
    if error:
        print(f"{idx:>4}  {truncate(name,30):<30}  {'오류':>6}          {error}")
    else:
        cer_str = f"{cer_val:.3f}" if cer_val is not None else "  N/A"
        print(f"{idx:>4}  {truncate(name,30):<30}  {elapsed:>5.1f}s  {cer_str:>6}  {truncate(pred, 60)}")


# ── 메인 실행 ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GOT-OCR 결과 확인 스크립트")

    # 입력 소스 (둘 중 하나 선택)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--uploads", action="store_true",
                     help=f"backend/uploads/ 폴더 전체 테스트 (기본: {DEFAULT_UPLOADS_DIR})")
    src.add_argument("--dir", metavar="PATH",
                     help="이미지 디렉터리 경로")
    src.add_argument("--image", metavar="FILE",
                     help="단일 이미지 파일")
    src.add_argument("--labels", metavar="FILE",
                     help="labels.json 파일 (정답 포함)")
    src.add_argument("--jsonl", metavar="FILE",
                     help="test.jsonl 파일 (정답 포함)")

    # 공통 옵션
    parser.add_argument("--images-root", metavar="DIR",
                        help="이미지 파일이 실제로 있는 루트 경로 (경로 리매핑)")
    parser.add_argument("--sample", type=int, metavar="N",
                        help="무작위 샘플 N개만 테스트 (labels/jsonl 모드)")
    parser.add_argument("--limit", type=int, metavar="N",
                        help="처음 N개만 테스트 (dir/uploads 모드)")
    parser.add_argument("--output", metavar="CSV",
                        help="결과를 CSV 파일로 저장")
    parser.add_argument("--show-gt", action="store_true",
                        help="정답 텍스트도 함께 출력")

    # 모델/워커 경로 (기본값: .env 기준)
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH,
                        help=f"GOT-OCR 모델 디렉터리 (기본: {DEFAULT_MODEL_PATH})")
    parser.add_argument("--worker-python", default=DEFAULT_WORKER_PYTHON,
                        help="argus-gotocr conda 환경 Python 경로")
    parser.add_argument("--worker-script", default=DEFAULT_WORKER_SCRIPT,
                        help="ocr_worker.py 경로")
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()
    random.seed(args.seed)

    # ── 입력 수집 ────────────────────────────────────────────────────
    if args.uploads:
        records = collect_from_dir(DEFAULT_UPLOADS_DIR, limit=args.limit)
    elif args.dir:
        records = collect_from_dir(args.dir, limit=args.limit)
    elif args.image:
        records = [{"image": args.image, "ground_truth": None}]
    elif args.labels:
        records = collect_from_labels(args.labels, args.images_root, args.sample)
    else:  # jsonl
        records = collect_from_jsonl(args.jsonl, args.images_root, args.sample)

    if not records:
        print("테스트할 이미지가 없습니다.", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== GOT-OCR 결과 확인 ({len(records)}개) ===\n")

    # ── 워커 시작 ────────────────────────────────────────────────────
    worker = OcrWorker(args.model_path, args.worker_python, args.worker_script)
    worker.start()

    # ── 추론 ─────────────────────────────────────────────────────────
    rows = []
    cer_scores = []
    errors = 0

    print_header()

    for i, rec in enumerate(records, 1):
        img_path = rec["image"]
        gt = rec.get("ground_truth")
        name = Path(img_path).name

        if not Path(img_path).exists():
            print_row(i, name, 0, None, "", f"파일 없음: {img_path}")
            rows.append({"#": i, "file": img_path, "pred": "", "ground_truth": gt or "",
                         "cer": "", "elapsed_sec": "", "error": "파일 없음"})
            errors += 1
            continue

        try:
            pred, elapsed = worker.recognize(img_path)
            cer_val = cer(pred, gt) if gt is not None else None
            if cer_val is not None:
                cer_scores.append(cer_val)
            print_row(i, name, elapsed, cer_val, pred, None)
            if args.show_gt and gt is not None:
                print(f"       GT: {truncate(gt, 90)}")
            rows.append({"#": i, "file": img_path, "pred": pred, "ground_truth": gt or "",
                         "cer": f"{cer_val:.4f}" if cer_val is not None else "",
                         "elapsed_sec": f"{elapsed:.2f}", "error": ""})
        except Exception as e:
            print_row(i, name, 0, None, "", str(e))
            rows.append({"#": i, "file": img_path, "pred": "", "ground_truth": gt or "",
                         "cer": "", "elapsed_sec": "", "error": str(e)})
            errors += 1

    worker.stop()

    # ── 요약 ─────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    ok = len(rows) - errors
    print(f"완료: {ok}개 성공 / {errors}개 오류 / 총 {len(rows)}개")
    if cer_scores:
        mean_cer = sum(cer_scores) / len(cer_scores)
        below_05 = sum(1 for c in cer_scores if c < 0.5) / len(cer_scores) * 100
        exact = sum(1 for c in cer_scores if c == 0.0) / len(cer_scores) * 100
        print(f"\nCER 통계 (정답 있는 {len(cer_scores)}개):")
        print(f"  평균 CER        : {mean_cer:.4f}")
        print(f"  CER < 0.5 비율  : {below_05:.1f}%")
        print(f"  완전 일치(EM)   : {exact:.1f}%")
        print(f"  최소 / 최대 CER : {min(cer_scores):.4f} / {max(cer_scores):.4f}")
    else:
        print("  (정답 텍스트 없음 — CER 계산 불가)")

    # ── CSV 저장 ─────────────────────────────────────────────────────
    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["#", "file", "elapsed_sec", "cer", "pred", "ground_truth", "error"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV 저장: {args.output}")


if __name__ == "__main__":
    main()
