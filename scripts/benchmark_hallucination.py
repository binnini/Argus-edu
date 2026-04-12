#!/usr/bin/env python3
"""
benchmark_hallucination.py — LLM 배치 할루시네이션 검증 정확도 측정.

HallucinationBatchService가 올바른 피드백(valid)과
의도적으로 틀린 피드백(hallucinated)을 얼마나 정확히 분류하는지 측정한다.

각 문제에 대해:
  - valid_feedback: 모범 풀이 기반, 실제 오류를 정확히 짚은 피드백
  - hallucinated_feedback: 잘못된 오류 분석 또는 틀린 교정 방향

측정 지표:
  - Precision: is_valid=False 판정 중 실제 hallucination 비율
  - Recall: 실제 hallucination 중 탐지된 비율
  - Accuracy: 전체 판정 정확도
  - 평균 confidence

실행:
  conda run -n argus-ocr python scripts/benchmark_hallucination.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from config import settings
from mlx_lm import load as mlx_load
from services.llm_client import LLMClient
from services.hallucination_batch import (
    HALLUCINATION_SYSTEM_PROMPT,
    HALLUCINATION_USER_TEMPLATE,
    MAX_TOKENS,
)

# ── 테스트 케이스 ──────────────────────────────────────────────────────────────
# 각 케이스: problem_id, reference_solution, grading_steps(오답 단계),
#            valid_feedback(올바른 피드백), hallucinated_feedback(틀린 피드백)

TEST_CASES = [
    {
        "problem_id": "E01",
        "level": "초등3",
        "reference_solution": "1단계: 일의 자리 8+5=13, 받아올림 1\n2단계: 십의 자리 4+7+1=12, 받아올림 1\n3단계: 백의 자리 3+2+1=6\n답: 623",
        "student_answer": "348 + 275 = 613",
        "grading_steps": [{"step": 1, "description": "받아올림 처리", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "십의 자리 계산에서 받아올림 1을 더하지 않았습니다. 4+7=11이 아니라 4+7+1(받아올림)=12로 계산해야 합니다."}],
            "correct_approach": [{"step": 1, "title": "받아올림 처리", "content": "일의 자리 8+5=13에서 받아올림 1이 생깁니다. 십의 자리 4+7=11에 받아올림 1을 더해 12가 됩니다."}],
            "key_concept": "받아올림은 반드시 윗 자리 계산에 포함해야 합니다.",
        },
        "hallucinated_feedback": {
            "student_mistakes": [{"step": 1, "description": "백의 자리 숫자를 잘못 읽어서 3+3=6으로 계산했습니다."}],  # 실제 오류와 다른 원인
            "correct_approach": [{"step": 1, "title": "백의 자리 계산", "content": "3+2=5이므로 백의 자리는 5입니다."}],  # 수학적으로 틀린 교정
            "key_concept": "각 자리 숫자를 정확히 읽는 것이 중요합니다.",
        },
    },
    {
        "problem_id": "E02",
        "level": "초등4",
        "reference_solution": "1단계: 공통분모 12 구하기\n2단계: 1/3=4/12, 1/4=3/12\n3단계: 4/12+3/12=7/12",
        "student_answer": "1/3 + 1/4 = 2/7",
        "grading_steps": [
            {"step": 1, "description": "공통분모 구하기", "earned": 0, "max": 1},
            {"step": 2, "description": "통분", "earned": 0, "max": 1},
        ],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "분모끼리 더하고(3+4=7) 분자끼리 더하는(1+1=2) 실수를 했습니다. 분수 덧셈은 통분이 먼저입니다."}],
            "correct_approach": [
                {"step": 1, "title": "공통분모 구하기", "content": "3과 4의 최소공배수인 12를 공통분모로 씁니다."},
                {"step": 2, "title": "통분 후 덧셈", "content": "1/3=4/12, 1/4=3/12로 바꾼 후 4/12+3/12=7/12"},
            ],
            "key_concept": "분수의 덧셈은 반드시 통분(공통분모 만들기)을 먼저 해야 합니다.",
        },
        "hallucinated_feedback": {
            "student_mistakes": [{"step": 1, "description": "분자를 잘못 계산했습니다."}],
            "correct_approach": [{"step": 1, "title": "분수 덧셈", "content": "분모는 그대로 두고 분자만 더합니다: 1+1=2, 답은 2/3입니다."}],  # 완전히 틀린 교정
            "key_concept": "분수 덧셈 시 분자끼리, 분모끼리 더합니다.",  # 잘못된 개념
        },
    },
    {
        "problem_id": "M01",
        "level": "중1",
        "reference_solution": "2x = 11 - 3 = 8\nx = 4",
        "student_answer": "2x + 3 = 11에서 2x = 14, x = 7",
        "grading_steps": [{"step": 1, "description": "이항", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "이항 시 3을 빼야 하는데 더했습니다. 좌변의 +3을 우변으로 이항하면 -3이 됩니다."}],
            "correct_approach": [{"step": 1, "title": "올바른 이항", "content": "2x + 3 = 11에서 3을 우변으로 이항: 2x = 11 - 3 = 8, x = 4"}],
            "key_concept": "이항할 때는 항의 부호가 반대로 바뀝니다.",
        },
        "hallucinated_feedback": {
            "student_mistakes": [{"step": 1, "description": "x의 계수 2를 나누는 과정에서 오류가 생겼습니다."}],  # 실제 오류 단계가 다름
            "correct_approach": [{"step": 1, "title": "양변 나누기", "content": "2x = 11이므로 x = 11/2 = 5.5입니다."}],  # 수학적으로 틀림
            "key_concept": "방정식에서 계수로 양변을 나눕니다.",
        },
    },
    {
        "problem_id": "M05",
        "level": "중3",
        "reference_solution": "x² - 5x + 6 = 0\n(x-2)(x-3) = 0\nx = 2 또는 x = 3",
        "student_answer": "x² - 5x + 6 = 0에서 (x-1)(x-6)=0, x=1 또는 x=6",
        "grading_steps": [{"step": 1, "description": "인수분해", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "인수분해가 잘못됐습니다. (x-1)(x-6)을 전개하면 x²-7x+6이 되어 원래 식 x²-5x+6과 다릅니다."}],
            "correct_approach": [{"step": 1, "title": "올바른 인수분해", "content": "두 수의 합이 -5, 곱이 6인 쌍을 찾으면 -2와 -3입니다. 따라서 (x-2)(x-3)=0"}],
            "key_concept": "인수분해 시 두 수의 합이 x의 계수, 곱이 상수항과 일치해야 합니다.",
        },
        "hallucinated_feedback": {
            "student_mistakes": [{"step": 1, "description": "근의 공식 적용에서 판별식 계산이 틀렸습니다."}],  # 학생은 인수분해를 사용했음
            "correct_approach": [{"step": 1, "title": "근의 공식", "content": "판별식 D = 25 - 24 = 1 > 0이므로 x = (5 ± 1) / 2 = 3 또는 2"}],
            "key_concept": "이차방정식은 근의 공식으로 풀 수 있습니다.",  # 틀린 원인 분석
        },
    },
    {
        "problem_id": "H01",
        "level": "고1",
        "reference_solution": "log₂8 = log₂2³ = 3·log₂2 = 3",
        "student_answer": "log₂8 = 8/2 = 4",
        "grading_steps": [{"step": 1, "description": "로그 정의 적용", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "로그를 단순 나눗셈으로 계산했습니다. log₂8은 '2를 몇 번 곱하면 8이 되는가'를 묻는 것입니다."}],
            "correct_approach": [{"step": 1, "title": "로그 정의", "content": "log₂8 = log₂2³ = 3 (2³=8이므로)"}],
            "key_concept": "logₐb는 'a를 몇 번 곱하면 b가 되는가'를 의미합니다.",
        },
        "hallucinated_feedback": {
            "student_mistakes": [{"step": 1, "description": "지수법칙에서 밑을 잘못 적용했습니다."}],
            "correct_approach": [{"step": 1, "title": "지수 변환", "content": "8 = 2³이므로 log₂8 = log₂2³ = 3·2 = 6입니다."}],  # 로그 법칙 오적용
            "key_concept": "로그의 지수법칙: logₐbⁿ = n·logₐb·a 입니다.",  # 틀린 공식
        },
    },
    {
        "problem_id": "E07",
        "level": "초등3",
        "reference_solution": "8 × 9 = 72이므로 72 ÷ 8 = 9",
        "student_answer": "72 ÷ 8 = 8",
        "grading_steps": [{"step": 1, "description": "나눗셈 계산", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "8 × 8 = 64이고, 72 ÷ 8 = 8이 되려면 64 ÷ 8 = 8이어야 합니다. 72는 8 × 9 = 72이므로 답은 9입니다."}],
            "correct_approach": [{"step": 1, "title": "곱셈 역산", "content": "8의 단 구구단: 8×9=72이므로 72÷8=9"}],
            "key_concept": "나눗셈은 곱셈의 역연산으로 확인할 수 있습니다.",
        },
        "hallucinated_feedback": {
            "student_mistakes": [{"step": 1, "description": "72를 8로 나누면 소수가 나오는데 반올림 오류가 있습니다."}],  # 72÷8은 정수
            "correct_approach": [{"step": 1, "title": "나눗셈", "content": "72 ÷ 8 = 9.5로 반올림하면 10입니다."}],  # 완전히 틀린 답
            "key_concept": "소수점 나눗셈에서는 반올림이 필요합니다.",
        },
    },
]


async def run_hallucination_benchmark():
    print("=" * 60)
    print("할루시네이션 검증 벤치마크")
    print(f"모델: {settings.mlx_model_path}")
    print(f"테스트 케이스: {len(TEST_CASES)}문제 × 2 (valid + hallucinated) = {len(TEST_CASES)*2}건")
    print("=" * 60)

    # MLX 모델 로드
    print("\nMLX 모델 로딩...")
    t0 = time.time()
    model, tokenizer = mlx_load(settings.mlx_model_path)
    llm = LLMClient(mlx_model=model, mlx_tokenizer=tokenizer)
    print(f"로딩 완료: {time.time()-t0:.1f}s\n")

    # 배치 입력 구성: valid(label=True) + hallucinated(label=False) 혼합
    batch_input = []
    ground_truth = {}   # id → expected is_valid

    for tc in TEST_CASES:
        vid = f"{tc['problem_id']}_valid"
        hid = f"{tc['problem_id']}_halluc"

        batch_input.append({
            "id": vid,
            "reference_solution": tc["reference_solution"],
            "grading_steps": tc["grading_steps"],
            "student_mistakes": tc["valid_feedback"]["student_mistakes"],
            "correct_approach": tc["valid_feedback"]["correct_approach"],
            "key_concept": tc["valid_feedback"]["key_concept"],
        })
        batch_input.append({
            "id": hid,
            "reference_solution": tc["reference_solution"],
            "grading_steps": tc["grading_steps"],
            "student_mistakes": tc["hallucinated_feedback"]["student_mistakes"],
            "correct_approach": tc["hallucinated_feedback"]["correct_approach"],
            "key_concept": tc["hallucinated_feedback"]["key_concept"],
        })
        ground_truth[vid] = True   # valid → is_valid 기대값: True
        ground_truth[hid] = False  # hallucinated → is_valid 기대값: False

    # LLM 호출
    print(f"배치 LLM 검증 호출 ({len(batch_input)}건)...")
    t1 = time.time()
    user_prompt = HALLUCINATION_USER_TEMPLATE.format(
        items_json=json.dumps(batch_input, ensure_ascii=False, indent=2)
    )
    try:
        response = await asyncio.wait_for(
            llm.chat(
                system_prompt=HALLUCINATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=settings.grading_model,
                max_tokens=MAX_TOKENS,
                temperature=0.1,
            ),
            timeout=settings.llm_timeout_seconds,
        )
    except Exception as e:
        print(f"LLM 호출 실패: {e}")
        return
    elapsed = time.time() - t1
    print(f"LLM 응답 완료: {elapsed:.1f}s\n")

    # 응답 파싱
    import re
    raw = response.text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if match:
        raw = match.group(0)
    try:
        verdicts = json.loads(raw)
    except Exception as e:
        # escape 수정 후 재시도
        raw2 = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
        try:
            verdicts = json.loads(raw2)
        except Exception:
            print(f"JSON 파싱 실패: {e}\n원문:\n{response.text[:500]}")
            return

    # 결과 분석
    verdict_map = {v["id"]: v for v in verdicts if isinstance(v.get("id"), str)}

    tp = tn = fp = fn = 0
    confidences = []
    rows = []

    print(f"{'ID':<20} {'기대':^8} {'판정':^8} {'정오':^6} {'confidence':^12} {'issues'}")
    print("-" * 80)

    for item_id, expected_valid in sorted(ground_truth.items()):
        v = verdict_map.get(item_id)
        if v is None:
            print(f"{item_id:<20} {'valid' if expected_valid else 'halluc':^8} {'N/A':^8} {'?':^6} {'N/A':^12} 판정 없음")
            fn += 1
            continue

        predicted_valid = bool(v.get("is_valid", True))
        confidence = float(v.get("confidence", 0.5))
        issues = v.get("issues", [])
        confidences.append(confidence)

        correct = (predicted_valid == expected_valid)
        mark = "✅" if correct else "❌"

        if expected_valid and predicted_valid:     tp += 1
        elif not expected_valid and not predicted_valid: tn += 1
        elif not expected_valid and predicted_valid:     fp += 1
        else:                                           fn += 1

        issue_str = issues[0][:40] if issues else ""
        print(f"{item_id:<20} {'valid' if expected_valid else 'halluc':^8} {'valid' if predicted_valid else 'halluc':^8} {mark:^6} {confidence:^12.2f} {issue_str}")

    total = tp + tn + fp + fn
    accuracy  = (tp + tn) / total if total else 0
    precision = tp / (tp + fp) if (tp + fp) else 0  # valid 판정 중 실제 valid
    recall    = tn / (tn + fn) if (tn + fn) else 0  # hallucination 중 탐지된 비율 (halluc recall)
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    avg_conf  = sum(confidences) / len(confidences) if confidences else 0

    print("\n" + "=" * 60)
    print("📊 결과 요약")
    print("=" * 60)
    print(f"  총 건수:        {total} (valid {len(TEST_CASES)}건, hallucinated {len(TEST_CASES)}건)")
    print(f"  정확도:         {accuracy*100:.1f}%  ({tp+tn}/{total})")
    print(f"  Valid 정확도:   {tp}/{len(TEST_CASES)} ({tp/len(TEST_CASES)*100:.0f}%) — 올바른 피드백을 valid로 판정")
    print(f"  Halluc 탐지율:  {tn}/{len(TEST_CASES)} ({tn/len(TEST_CASES)*100:.0f}%) — 틀린 피드백을 탐지")
    print(f"  FP (놓친 halluc): {fp}")
    print(f"  FN (오분류 valid): {fn}")
    print(f"  평균 confidence: {avg_conf:.2f}")
    print(f"  LLM 처리 시간:  {elapsed:.1f}s ({elapsed/len(batch_input):.1f}s/건)")
    print()

    # SLA 판단 기준
    if accuracy >= 0.80:
        print("✅ 할루시네이션 검증 정확도 80% 이상 — 실서비스 적용 가능")
    else:
        print("⚠️  정확도 80% 미만 — Claude API 전환 또는 프롬프트 튜닝 필요 (ADR-026 변경 조건)")


if __name__ == "__main__":
    asyncio.run(run_hallucination_benchmark())
