#!/usr/bin/env python3
"""
benchmark_hallucination.py — LLM 배치 할루시네이션 검증 정확도 측정.

HallucinationBatchService가 올바른 피드백(valid)과
의도적으로 틀린 피드백(hallucinated)을 얼마나 정확히 분류하는지 측정한다.

각 문제에 대해:
  - valid_feedback: 모범 풀이 기반, 실제 오류를 정확히 짚은 피드백
  - hallucinated_feedback: 잘못된 오류 분석 또는 틀린 교정 방향

할루시네이션 패턴 유형 (halluc_type):
  A) wrong_cause  — 오류 원인을 다른 단계/이유로 잘못 지적
  B) wrong_math   — 수학적으로 틀린 교정 방향 제시
  C) wrong_concept — 핵심 개념 자체가 틀림
  D) off_topic    — 학생 풀이와 무관한 내용을 오류로 지적

측정 지표:
  - Accuracy: 전체 판정 정확도
  - Valid 정확도: 올바른 피드백을 valid로 판정한 비율
  - Halluc 탐지율: 틀린 피드백을 탐지한 비율
  - 패턴별 탐지율: A/B/C/D 유형별 분석
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
# halluc_type: A=wrong_cause, B=wrong_math, C=wrong_concept, D=off_topic
# 총 20문제 × 2 = 40건 (초등 6, 중학 7, 고등 7)

TEST_CASES = [
    # ── 초등 ──────────────────────────────────────────────────────────────────
    {
        "problem_id": "E01",
        "level": "초등3",
        "halluc_type": "A",
        "reference_solution": "1단계: 일의 자리 8+5=13, 받아올림 1\n2단계: 십의 자리 4+7+1=12, 받아올림 1\n3단계: 백의 자리 3+2+1=6\n답: 623",
        "student_answer": "348 + 275 = 613",
        "grading_steps": [{"step": 1, "description": "받아올림 처리", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "십의 자리 계산에서 받아올림 1을 더하지 않았습니다. 4+7=11이 아니라 4+7+1(받아올림)=12로 계산해야 합니다."}],
            "correct_approach": [{"step": 1, "title": "받아올림 처리", "content": "일의 자리 8+5=13에서 받아올림 1이 생깁니다. 십의 자리 4+7=11에 받아올림 1을 더해 12가 됩니다."}],
            "key_concept": "받아올림은 반드시 윗 자리 계산에 포함해야 합니다.",
        },
        "hallucinated_feedback": {
            # A: 실제 오류(십의 자리 받아올림)와 다른 원인(백의 자리 오독)을 지적
            "student_mistakes": [{"step": 1, "description": "백의 자리 숫자를 잘못 읽어서 3+3=6으로 계산했습니다."}],
            "correct_approach": [{"step": 1, "title": "백의 자리 계산", "content": "3+2=5이므로 백의 자리는 5입니다."}],
            "key_concept": "각 자리 숫자를 정확히 읽는 것이 중요합니다.",
        },
    },
    {
        "problem_id": "E02",
        "level": "초등4",
        "halluc_type": "C",
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
            # C: 핵심 개념 자체가 틀림 — "분자끼리, 분모끼리 더한다"는 잘못된 규칙 제시
            "student_mistakes": [{"step": 1, "description": "분자를 잘못 계산했습니다."}],
            "correct_approach": [{"step": 1, "title": "분수 덧셈", "content": "분모는 그대로 두고 분자만 더합니다: 1+1=2, 답은 2/3입니다."}],
            "key_concept": "분수 덧셈 시 분자끼리, 분모끼리 더합니다.",
        },
    },
    {
        "problem_id": "E03",
        "level": "초등5",
        "halluc_type": "B",
        "reference_solution": "1단계: 0.4 + 0.7 = 1.1\n2단계: 소수점 자리 정렬 후 1.1",
        "student_answer": "0.4 + 0.7 = 0.11",
        "grading_steps": [{"step": 1, "description": "소수 덧셈 자리값 처리", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "소수점 아래 자리수를 단순히 붙여서 0.11이라고 했습니다. 4+7=11이므로 소수 한 자리 올림이 발생해 1.1이 됩니다."}],
            "correct_approach": [{"step": 1, "title": "소수 덧셈", "content": "0.4+0.7은 4+7=11에서 소수 한 자리이므로 1.1입니다. 1이 일의 자리로 올라갑니다."}],
            "key_concept": "소수 덧셈도 자연수처럼 자리값을 맞춰 받아올림합니다.",
        },
        "hallucinated_feedback": {
            # B: 수학적으로 틀린 교정 — 소수점 이동 규칙을 잘못 설명
            "student_mistakes": [{"step": 1, "description": "소수점 위치를 한 칸 오른쪽으로 이동하지 않았습니다."}],
            "correct_approach": [{"step": 1, "title": "소수점 이동", "content": "0.4+0.7을 계산할 때 소수점을 오른쪽으로 한 칸 옮기면 4+7=11, 다시 왼쪽으로 두 칸 옮기면 0.11입니다."}],
            "key_concept": "소수 덧셈에서는 소수점을 두 칸 왼쪽으로 이동합니다.",
        },
    },
    {
        "problem_id": "E04",
        "level": "초등5",
        "halluc_type": "A",
        "reference_solution": "1단계: 전체 20개 중 8개이므로 비율 = 8/20\n2단계: 8÷20 = 0.4\n3단계: 백분율 = 0.4 × 100 = 40%",
        "student_answer": "8개 중 20개이므로 20/8 = 2.5, 250%",
        "grading_steps": [
            {"step": 1, "description": "분자/분모 설정", "earned": 0, "max": 1},
            {"step": 2, "description": "백분율 변환", "earned": 0, "max": 1},
        ],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "비교량(8)과 기준량(20)의 위치가 바뀌었습니다. 비율은 (비교량)÷(기준량) = 8÷20이어야 합니다."}],
            "correct_approach": [
                {"step": 1, "title": "비율 설정", "content": "전체 20개 중 8개이므로 비율 = 8/20 = 0.4"},
                {"step": 2, "title": "백분율", "content": "0.4 × 100 = 40%"},
            ],
            "key_concept": "비율 = 비교량 ÷ 기준량. 기준량이 분모입니다.",
        },
        "hallucinated_feedback": {
            # A: 실제 오류(분자/분모 역전)가 아닌 다른 단계(백분율 변환 공식)를 지적
            "student_mistakes": [{"step": 1, "description": "백분율로 변환할 때 100을 곱하지 않고 나눴습니다."}],
            "correct_approach": [{"step": 1, "title": "백분율 변환", "content": "소수를 백분율로 바꾸려면 100으로 나눕니다. 2.5 ÷ 100 = 0.025%"}],
            "key_concept": "백분율 = 소수 ÷ 100입니다.",
        },
    },
    {
        "problem_id": "E05",
        "level": "초등4",
        "halluc_type": "D",
        "reference_solution": "1단계: 23 × 4 = 92\n2단계: 23 × 10 = 230\n3단계: 92 + 230 = 322\n답: 322",
        "student_answer": "23 × 14 = 292",
        "grading_steps": [
            {"step": 1, "description": "일의 자리 곱", "earned": 1, "max": 1},
            {"step": 2, "description": "십의 자리 곱", "earned": 0, "max": 1},
        ],
        "valid_feedback": {
            "student_mistakes": [{"step": 2, "description": "23×14에서 십의 자리 1과 곱할 때 23×1=23으로만 더했습니다. 십의 자리이므로 23×10=230을 더해야 합니다."}],
            "correct_approach": [
                {"step": 1, "title": "일의 자리", "content": "23×4=92 (정확함)"},
                {"step": 2, "title": "십의 자리", "content": "23×10=230 (자리값 반영). 92+230=322"},
            ],
            "key_concept": "두 자리 수 곱셈에서 십의 자리 곱은 ×10을 반영해야 합니다.",
        },
        "hallucinated_feedback": {
            # D: 학생 풀이(자리값 누락)와 무관하게 덧셈 오류를 지적
            "student_mistakes": [{"step": 2, "description": "92와 23을 더하는 과정에서 받아올림을 빠뜨렸습니다."}],
            "correct_approach": [{"step": 2, "title": "세로 덧셈", "content": "92+23=115이므로 답은 115입니다."}],
            "key_concept": "세로 덧셈에서 받아올림을 정확히 처리해야 합니다.",
        },
    },
    {
        "problem_id": "E06",
        "level": "초등5",
        "halluc_type": "C",
        "reference_solution": "1단계: 약분: 12/18 = 2/3 (GCD=6)\n2단계: 기약분수 2/3",
        "student_answer": "12/18 = 6/9",
        "grading_steps": [{"step": 1, "description": "최대공약수로 완전 약분", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "12와 18을 2로만 나눠 6/9로 약분했습니다. 6/9는 다시 3으로 나눌 수 있으므로 기약분수가 아닙니다. 최대공약수 6으로 한 번에 약분해야 합니다."}],
            "correct_approach": [{"step": 1, "title": "최대공약수 약분", "content": "12와 18의 최대공약수는 6입니다. 12÷6=2, 18÷6=3이므로 기약분수는 2/3입니다."}],
            "key_concept": "기약분수는 최대공약수로 나눠 더 이상 약분되지 않는 분수입니다.",
        },
        "hallucinated_feedback": {
            # C: 기약분수 개념 자체를 틀리게 설명 — "분자가 1인 분수"라고 오정의
            "student_mistakes": [{"step": 1, "description": "기약분수는 분자가 1이어야 하는데 분자가 6입니다."}],
            "correct_approach": [{"step": 1, "title": "기약분수 만들기", "content": "분자를 1로 만들려면 12/18 = 1/1.5이지만, 분수에서 분모는 자연수여야 하므로 1/2으로 씁니다."}],
            "key_concept": "기약분수는 분자가 반드시 1인 분수입니다.",
        },
    },

    # ── 중학 ──────────────────────────────────────────────────────────────────
    {
        "problem_id": "M01",
        "level": "중1",
        "halluc_type": "A",
        "reference_solution": "2x = 11 - 3 = 8\nx = 4",
        "student_answer": "2x + 3 = 11에서 2x = 14, x = 7",
        "grading_steps": [{"step": 1, "description": "이항", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "이항 시 3을 빼야 하는데 더했습니다. 좌변의 +3을 우변으로 이항하면 -3이 됩니다."}],
            "correct_approach": [{"step": 1, "title": "올바른 이항", "content": "2x + 3 = 11에서 3을 우변으로 이항: 2x = 11 - 3 = 8, x = 4"}],
            "key_concept": "이항할 때는 항의 부호가 반대로 바뀝니다.",
        },
        "hallucinated_feedback": {
            # A: 실제 오류(이항 부호)가 아닌 다른 단계(계수 나누기) 지적
            "student_mistakes": [{"step": 1, "description": "x의 계수 2를 나누는 과정에서 오류가 생겼습니다."}],
            "correct_approach": [{"step": 1, "title": "양변 나누기", "content": "2x = 11이므로 x = 11/2 = 5.5입니다."}],
            "key_concept": "방정식에서 계수로 양변을 나눕니다.",
        },
    },
    {
        "problem_id": "M02",
        "level": "중1",
        "halluc_type": "C",
        "reference_solution": "(-3) × (-4) = +12 (음수 × 음수 = 양수)",
        "student_answer": "(-3) × (-4) = -12",
        "grading_steps": [{"step": 1, "description": "음수 곱셈 부호 규칙", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "음수×음수의 결과를 음수로 잘못 계산했습니다. 음수끼리의 곱은 양수입니다."}],
            "correct_approach": [{"step": 1, "title": "부호 규칙", "content": "(-3)×(-4): 절댓값 3×4=12, 음수×음수=양수이므로 답은 +12"}],
            "key_concept": "음수×음수=양수, 음수×양수=음수입니다.",
        },
        "hallucinated_feedback": {
            # C: 부호 규칙 자체를 거꾸로 제시
            "student_mistakes": [{"step": 1, "description": "두 수의 절댓값 곱을 잘못 계산했습니다."}],
            "correct_approach": [{"step": 1, "title": "음수 곱셈", "content": "음수끼리 곱하면 항상 음수입니다. (-3)×(-4) = -(3×4) = -12"}],
            "key_concept": "두 음수를 곱하면 음수가 됩니다.",
        },
    },
    {
        "problem_id": "M03",
        "level": "중2",
        "halluc_type": "B",
        "reference_solution": "x+y=5 ... (1)\n2x-y=4 ... (2)\n(1)+(2): 3x=9, x=3\n(1)에 대입: y=5-3=2\n답: x=3, y=2",
        "student_answer": "x+y=5, 2x-y=4를 더하면 3x-0=9? 아니, x=3, y=4",
        "grading_steps": [
            {"step": 1, "description": "두 식 더하기", "earned": 1, "max": 1},
            {"step": 2, "description": "x값 대입하여 y 계산", "earned": 0, "max": 1},
        ],
        "valid_feedback": {
            "student_mistakes": [{"step": 2, "description": "x=3을 (1)에 대입할 때 3+y=5에서 y=5+3=8이 아니라 y=5-3=2입니다. 이항 시 부호가 바뀝니다."}],
            "correct_approach": [
                {"step": 1, "title": "가감법", "content": "두 식을 더해 3x=9, x=3 (정확함)"},
                {"step": 2, "title": "대입", "content": "x=3을 x+y=5에 대입: 3+y=5, y=2"},
            ],
            "key_concept": "연립방정식에서 한 변수를 구한 뒤 원래 식에 대입합니다.",
        },
        "hallucinated_feedback": {
            # B: 수학적으로 틀린 교정 — 두 식을 곱해야 한다고 잘못 안내
            "student_mistakes": [{"step": 1, "description": "두 식을 더하면 안 됩니다. 가감법에서는 계수를 맞춰 곱해야 합니다."}],
            "correct_approach": [{"step": 1, "title": "곱셈 후 소거", "content": "(1)×2: 2x+2y=10, (2)×1: 2x-y=4. 두 식을 곱하면 4x²-2y²=40이므로 x=√10"}],
            "key_concept": "연립방정식은 두 식을 곱하여 변수를 소거합니다.",
        },
    },
    {
        "problem_id": "M04",
        "level": "중2",
        "halluc_type": "A",
        "reference_solution": "기울기 = (y변화량)/(x변화량) = (5-1)/(3-1) = 4/2 = 2",
        "student_answer": "두 점 (1,1),(3,5)를 지나는 직선의 기울기 = (3-1)/(5-1) = 2/4 = 1/2",
        "grading_steps": [{"step": 1, "description": "기울기 공식 분자/분모", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "기울기 공식에서 분자와 분모가 바뀌었습니다. 기울기 = (y₂-y₁)/(x₂-x₁)인데 x 차이를 분자에, y 차이를 분모에 놓았습니다."}],
            "correct_approach": [{"step": 1, "title": "기울기 공식", "content": "기울기 = (y₂-y₁)/(x₂-x₁) = (5-1)/(3-1) = 4/2 = 2"}],
            "key_concept": "기울기 = y의 변화량 ÷ x의 변화량 (분자가 y차이, 분모가 x차이).",
        },
        "hallucinated_feedback": {
            # A: 실제 오류(분자분모 역전)가 아닌 다른 점을 오류 원인으로 지적
            "student_mistakes": [{"step": 1, "description": "좌표 (1,1)에서 x좌표와 y좌표를 반대로 읽었습니다."}],
            "correct_approach": [{"step": 1, "title": "좌표 읽기", "content": "점 (1,1)은 x=1, y=1입니다. 다시 계산하면 (1-3)/(1-5) = -2/-4 = 1/2입니다."}],
            "key_concept": "좌표 (x, y)에서 첫 번째 값이 x, 두 번째 값이 y입니다.",
        },
    },
    {
        "problem_id": "M05",
        "level": "중3",
        "halluc_type": "D",
        "reference_solution": "x² - 5x + 6 = 0\n(x-2)(x-3) = 0\nx = 2 또는 x = 3",
        "student_answer": "x² - 5x + 6 = 0에서 (x-1)(x-6)=0, x=1 또는 x=6",
        "grading_steps": [{"step": 1, "description": "인수분해", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "인수분해가 잘못됐습니다. (x-1)(x-6)을 전개하면 x²-7x+6이 되어 원래 식 x²-5x+6과 다릅니다."}],
            "correct_approach": [{"step": 1, "title": "올바른 인수분해", "content": "두 수의 합이 -5, 곱이 6인 쌍을 찾으면 -2와 -3입니다. 따라서 (x-2)(x-3)=0"}],
            "key_concept": "인수분해 시 두 수의 합이 x의 계수, 곱이 상수항과 일치해야 합니다.",
        },
        "hallucinated_feedback": {
            # D: 학생은 인수분해를 사용했는데 근의 공식 오류로 엉뚱하게 지적
            "student_mistakes": [{"step": 1, "description": "근의 공식 적용에서 판별식 계산이 틀렸습니다."}],
            "correct_approach": [{"step": 1, "title": "근의 공식", "content": "판별식 D = 25 - 24 = 1 > 0이므로 x = (5 ± 1) / 2 = 3 또는 2"}],
            "key_concept": "이차방정식은 근의 공식으로 풀어야 합니다.",
        },
    },
    {
        "problem_id": "M06",
        "level": "중2",
        "halluc_type": "B",
        "reference_solution": "피타고라스 정리: c² = a² + b²\nc² = 3² + 4² = 9 + 16 = 25\nc = 5",
        "student_answer": "직각삼각형에서 c = 3 + 4 = 7",
        "grading_steps": [{"step": 1, "description": "피타고라스 정리 적용", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "피타고라스 정리는 c²=a²+b²인데 변의 길이를 그냥 더했습니다. 제곱과 제곱근을 사용해야 합니다."}],
            "correct_approach": [{"step": 1, "title": "피타고라스 정리", "content": "c² = 3² + 4² = 9 + 16 = 25, c = √25 = 5"}],
            "key_concept": "직각삼각형에서 빗변² = 나머지 두 변의 제곱의 합입니다.",
        },
        "hallucinated_feedback": {
            # B: 수학적으로 틀린 공식 제시 — c = √(a+b)라고 잘못 안내
            "student_mistakes": [{"step": 1, "description": "두 변의 합에 제곱근을 취하지 않았습니다."}],
            "correct_approach": [{"step": 1, "title": "피타고라스 공식", "content": "c = √(a+b) = √(3+4) = √7 ≈ 2.65입니다."}],
            "key_concept": "직각삼각형의 빗변 = √(두 변의 합)입니다.",
        },
    },
    {
        "problem_id": "M07",
        "level": "중3",
        "halluc_type": "C",
        "reference_solution": "x² + 6x + 9 = (x+3)²\n완전제곱식: (x+3)²",
        "student_answer": "x² + 6x + 9 = (x+6)²",
        "grading_steps": [{"step": 1, "description": "완전제곱식 인수분해", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "(x+6)²을 전개하면 x²+12x+36인데 원식은 x²+6x+9이므로 다릅니다. x²+6x+9 = (x+3)²임을 확인하세요."}],
            "correct_approach": [{"step": 1, "title": "완전제곱식", "content": "x²+bx+c = (x+b/2)² 형태. b=6이므로 b/2=3, 검증: (x+3)²=x²+6x+9 ✓"}],
            "key_concept": "x²+bx+(b/2)² = (x+b/2)². 상수항은 (b/2)²이어야 합니다.",
        },
        "hallucinated_feedback": {
            # C: 완전제곱식 공식 자체를 잘못 제시 — b/2가 아닌 b를 그대로 쓴다고 설명
            "student_mistakes": [{"step": 1, "description": "완전제곱식에서 괄호 안의 수를 잘못 구했습니다."}],
            "correct_approach": [{"step": 1, "title": "완전제곱식 공식", "content": "x²+bx+c = (x+b)²이므로 x²+6x+9 = (x+6)². 학생의 답이 맞습니다."}],
            "key_concept": "완전제곱식: x²+bx+c = (x+b)².",
        },
    },

    # ── 고등 ──────────────────────────────────────────────────────────────────
    {
        "problem_id": "H01",
        "level": "고1",
        "halluc_type": "B",
        "reference_solution": "log₂8 = log₂2³ = 3·log₂2 = 3",
        "student_answer": "log₂8 = 8/2 = 4",
        "grading_steps": [{"step": 1, "description": "로그 정의 적용", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "로그를 단순 나눗셈으로 계산했습니다. log₂8은 '2를 몇 번 곱하면 8이 되는가'를 묻는 것입니다."}],
            "correct_approach": [{"step": 1, "title": "로그 정의", "content": "log₂8 = log₂2³ = 3 (2³=8이므로)"}],
            "key_concept": "logₐb는 'a를 몇 번 곱하면 b가 되는가'를 의미합니다.",
        },
        "hallucinated_feedback": {
            # B: 로그 법칙을 수학적으로 틀리게 적용
            "student_mistakes": [{"step": 1, "description": "지수법칙에서 밑을 잘못 적용했습니다."}],
            "correct_approach": [{"step": 1, "title": "지수 변환", "content": "8 = 2³이므로 log₂8 = log₂2³ = 3·2 = 6입니다."}],
            "key_concept": "로그의 지수법칙: logₐbⁿ = n·logₐb·a 입니다.",
        },
    },
    {
        "problem_id": "H02",
        "level": "고1",
        "halluc_type": "A",
        "reference_solution": "y = 2(x-1)² + 3\n꼭짓점: (1, 3)",
        "student_answer": "y = 2x² - 4x + 5에서 꼭짓점 x = 4/(2×2) = 1, y = 2(1)² - 4(1) + 5 = 3. 꼭짓점 (1, 3) — 정답",
        "grading_steps": [
            {"step": 1, "description": "꼭짓점 x좌표", "earned": 1, "max": 1},
            {"step": 2, "description": "꼭짓점 y좌표", "earned": 0, "max": 1},
        ],
        "valid_feedback": {
            "student_mistakes": [],
            "correct_approach": [
                {"step": 1, "title": "꼭짓점 x좌표", "content": "x = -b/2a = 4/(2×2) = 1 (정확)"},
                {"step": 2, "title": "꼭짓점 y좌표", "content": "y = 2(1)²-4(1)+5 = 3 (정확)"},
            ],
            "key_concept": "이차함수 y=ax²+bx+c의 꼭짓점 x좌표는 -b/2a입니다.",
        },
        "hallucinated_feedback": {
            # A: 정답인 풀이를 틀렸다고 지적하며 엉뚱한 오류 원인 제시
            "student_mistakes": [{"step": 2, "description": "꼭짓점 y좌표를 구할 때 x=1을 대입하지 않고 원점의 y절편을 사용했습니다."}],
            "correct_approach": [{"step": 2, "title": "y절편 이용", "content": "꼭짓점 y좌표는 y절편 c=5이므로 꼭짓점은 (1, 5)입니다."}],
            "key_concept": "이차함수의 꼭짓점 y좌표는 y절편과 같습니다.",
        },
    },
    {
        "problem_id": "H03",
        "level": "고2",
        "halluc_type": "B",
        "reference_solution": "f(x) = x³ - 3x\nf'(x) = 3x² - 3",
        "student_answer": "f(x) = x³ - 3x에서 f'(x) = 3x³ - 3",
        "grading_steps": [{"step": 1, "description": "도함수 계산", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "x³을 미분할 때 지수를 내리지 않았습니다. x³의 도함수는 3x²이지 3x³이 아닙니다."}],
            "correct_approach": [{"step": 1, "title": "멱함수 미분", "content": "xⁿ의 도함수는 n·xⁿ⁻¹. x³ → 3x², -3x → -3. 따라서 f'(x) = 3x² - 3"}],
            "key_concept": "멱함수 미분: (xⁿ)' = n·xⁿ⁻¹ (지수를 앞으로 내리고 지수에서 1을 뺍니다).",
        },
        "hallucinated_feedback": {
            # B: 미분 공식 자체를 잘못 제시
            "student_mistakes": [{"step": 1, "description": "미분 시 상수항을 제거하지 않았습니다."}],
            "correct_approach": [{"step": 1, "title": "미분 공식", "content": "xⁿ의 미분은 n·xⁿ입니다. x³ → 3·x³, -3x → -3·x. 따라서 f'(x) = 3x³ - 3x"}],
            "key_concept": "멱함수 미분: (xⁿ)' = n·xⁿ (지수는 그대로 유지).",
        },
    },
    {
        "problem_id": "H04",
        "level": "고1",
        "halluc_type": "C",
        "reference_solution": "A={1,2,3,4}, B={3,4,5,6}\nA∩B = {3,4}\nA∪B = {1,2,3,4,5,6}",
        "student_answer": "A∩B = {1,2,3,4,5,6}, A∪B = {3,4}",
        "grading_steps": [
            {"step": 1, "description": "교집합", "earned": 0, "max": 1},
            {"step": 2, "description": "합집합", "earned": 0, "max": 1},
        ],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "교집합(∩)과 합집합(∪)의 의미를 바꿔서 적용했습니다. ∩는 공통 원소, ∪는 모든 원소를 모은 집합입니다."}],
            "correct_approach": [
                {"step": 1, "title": "교집합", "content": "A∩B = A와 B에 모두 속하는 원소 = {3,4}"},
                {"step": 2, "title": "합집합", "content": "A∪B = A 또는 B에 속하는 원소 = {1,2,3,4,5,6}"},
            ],
            "key_concept": "∩(교집합)은 공통 원소, ∪(합집합)은 두 집합의 모든 원소입니다.",
        },
        "hallucinated_feedback": {
            # C: 집합 기호 정의 자체를 틀리게 제시
            "student_mistakes": [{"step": 1, "description": "원소 나열 순서가 잘못됐습니다."}],
            "correct_approach": [
                {"step": 1, "title": "교집합 ∩", "content": "A∩B는 A와 B를 합친 집합 = {1,2,3,4,5,6}"},
                {"step": 2, "title": "합집합 ∪", "content": "A∪B는 두 집합의 공통 원소 = {3,4}"},
            ],
            "key_concept": "∩는 합집합, ∪는 교집합을 나타냅니다.",
        },
    },
    {
        "problem_id": "H05",
        "level": "고2",
        "halluc_type": "D",
        "reference_solution": "sin30° = 1/2\ncos60° = 1/2\nsin30° + cos60° = 1/2 + 1/2 = 1",
        "student_answer": "sin30° = √3/2, cos60° = 1/2이므로 sin30°+cos60° = (√3+1)/2",
        "grading_steps": [{"step": 1, "description": "sin30° 값", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "sin30°=1/2인데 sin60°=√3/2로 혼동했습니다. 30°와 60°의 sin/cos 값을 바꿔서 암기한 것 같습니다."}],
            "correct_approach": [{"step": 1, "title": "삼각비 암기", "content": "sin30°=1/2, sin60°=√3/2, cos30°=√3/2, cos60°=1/2. 따라서 sin30°+cos60°=1/2+1/2=1"}],
            "key_concept": "sin30°=1/2, sin60°=√3/2. 30°와 60°의 값을 정확히 구별하세요.",
        },
        "hallucinated_feedback": {
            # D: 실제 오류(sin30° 값 혼동)와 무관한 공식 오류를 지적
            "student_mistakes": [{"step": 1, "description": "sin과 cos를 더할 때 피타고라스 항등식을 사용하지 않았습니다."}],
            "correct_approach": [{"step": 1, "title": "항등식 활용", "content": "sin²θ+cos²θ=1이므로 sinθ+cosθ = √(1+2sinθcosθ) = √(1+sin60°) ≈ 1.37"}],
            "key_concept": "삼각함수 덧셈 시 피타고라스 항등식 sin²θ+cos²θ=1을 먼저 적용합니다.",
        },
    },
    {
        "problem_id": "H06",
        "level": "고2",
        "halluc_type": "A",
        "reference_solution": "등차수열 공차 d = (a₅-a₁)/(5-1) = (17-5)/4 = 3\na₁₀ = a₁ + 9d = 5 + 27 = 32",
        "student_answer": "a₁=5, a₅=17이면 d=(17-5)/5=12/5=2.4, a₁₀=5+9×2.4=26.6",
        "grading_steps": [{"step": 1, "description": "공차 계산", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "공차를 구할 때 나누는 수를 항수(5) 대신 항 번호 차이(5-1=4)로 나눠야 합니다. a₁에서 a₅까지는 4번의 공차 간격이 있습니다."}],
            "correct_approach": [{"step": 1, "title": "공차 계산", "content": "d = (a₅-a₁)/(5-1) = (17-5)/4 = 3. a₁₀ = 5 + 9×3 = 32"}],
            "key_concept": "aₙ = a₁ + (n-1)d이므로 공차 d = (aₙ-a₁)/(n-1)입니다.",
        },
        "hallucinated_feedback": {
            # A: 실제 오류(나누는 수)가 아닌 a₁₀ 대입 단계를 오류 원인으로 지적
            "student_mistakes": [{"step": 1, "description": "a₁₀을 구할 때 9d 대신 10d를 곱해야 합니다."}],
            "correct_approach": [{"step": 1, "title": "일반항 공식", "content": "a₁₀ = a₁ + 10d = 5 + 10×2.4 = 29"}],
            "key_concept": "등차수열 일반항: aₙ = a₁ + n·d (n을 그대로 곱합니다).",
        },
    },
    {
        "problem_id": "H07",
        "level": "고2",
        "halluc_type": "C",
        "reference_solution": "두 사건 독립: P(A∩B) = P(A)×P(B) = 0.4×0.3 = 0.12\nP(A∪B) = P(A)+P(B)-P(A∩B) = 0.4+0.3-0.12 = 0.58",
        "student_answer": "P(A∪B) = P(A)+P(B) = 0.4+0.3 = 0.7",
        "grading_steps": [
            {"step": 1, "description": "독립사건 교집합 계산", "earned": 0, "max": 1},
            {"step": 2, "description": "합사건 확률 공식", "earned": 0, "max": 1},
        ],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "두 사건이 독립이라도 배반사건이 아니므로 P(A∩B)를 빼야 합니다. P(A)+P(B)만 더하면 P(A∩B) 부분이 중복 계산됩니다."}],
            "correct_approach": [
                {"step": 1, "title": "교집합 계산", "content": "독립사건: P(A∩B) = P(A)×P(B) = 0.4×0.3 = 0.12"},
                {"step": 2, "title": "합사건 공식", "content": "P(A∪B) = 0.4+0.3-0.12 = 0.58"},
            ],
            "key_concept": "P(A∪B) = P(A)+P(B)-P(A∩B). 독립사건이라도 교집합을 빼야 합니다.",
        },
        "hallucinated_feedback": {
            # C: 독립과 배반의 개념 혼동 — 독립이면 교집합이 0이라고 잘못 정의
            "student_mistakes": [{"step": 1, "description": "독립사건에서 P(A∩B)를 잘못 계산했습니다."}],
            "correct_approach": [
                {"step": 1, "title": "독립사건의 교집합", "content": "두 사건이 독립이면 서로 영향을 주지 않으므로 P(A∩B) = 0입니다."},
                {"step": 2, "title": "합사건", "content": "P(A∪B) = P(A)+P(B)-0 = 0.7. 학생의 답이 맞습니다."},
            ],
            "key_concept": "독립사건은 배반사건이므로 P(A∩B)=0입니다.",
        },
    },
    {
        "problem_id": "E07",
        "level": "초등3",
        "halluc_type": "B",
        "reference_solution": "8 × 9 = 72이므로 72 ÷ 8 = 9",
        "student_answer": "72 ÷ 8 = 8",
        "grading_steps": [{"step": 1, "description": "나눗셈 계산", "earned": 0, "max": 1}],
        "valid_feedback": {
            "student_mistakes": [{"step": 1, "description": "8 × 8 = 64이고, 72 ÷ 8 = 8이 되려면 8×8=72여야 하는데 실제로는 8×9=72입니다."}],
            "correct_approach": [{"step": 1, "title": "곱셈 역산", "content": "8의 단 구구단: 8×9=72이므로 72÷8=9"}],
            "key_concept": "나눗셈은 곱셈의 역연산으로 확인할 수 있습니다.",
        },
        "hallucinated_feedback": {
            # B: 72÷8이 정수인데 소수 연산 오류로 틀리게 교정
            "student_mistakes": [{"step": 1, "description": "72를 8로 나누면 소수가 나오는데 반올림 오류가 있습니다."}],
            "correct_approach": [{"step": 1, "title": "나눗셈", "content": "72 ÷ 8 = 9.5로 반올림하면 10입니다."}],
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
    ground_truth = {}    # id → expected is_valid
    halluc_type_map = {} # id → halluc_type (hallucinated 케이스만)

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
        ground_truth[vid] = True
        ground_truth[hid] = False
        halluc_type_map[hid] = tc.get("halluc_type", "?")

    # 40건을 두 배치(20건씩)로 나눠 호출 — MAX_TOKENS(1024) 초과 방지
    BATCH_SPLIT = 20
    all_verdicts: list[dict] = []
    total_elapsed = 0.0

    import re
    for batch_idx, start in enumerate(range(0, len(batch_input), BATCH_SPLIT)):
        chunk = batch_input[start:start + BATCH_SPLIT]
        print(f"배치 {batch_idx+1} LLM 호출 ({len(chunk)}건)...")
        t1 = time.time()
        user_prompt = HALLUCINATION_USER_TEMPLATE.format(
            items_json=json.dumps(chunk, ensure_ascii=False, indent=2)
        )
        try:
            response = await asyncio.wait_for(
                llm.chat(
                    system_prompt=HALLUCINATION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    model=settings.grading_model,
                    max_tokens=MAX_TOKENS * 2,   # 20건이므로 토큰 여유
                    temperature=0.1,
                ),
                timeout=settings.llm_timeout_seconds,
            )
        except Exception as e:
            print(f"배치 {batch_idx+1} LLM 호출 실패: {e}")
            return
        chunk_elapsed = time.time() - t1
        total_elapsed += chunk_elapsed
        print(f"  완료: {chunk_elapsed:.1f}s")

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
            raw2 = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
            try:
                verdicts = json.loads(raw2)
            except Exception:
                print(f"배치 {batch_idx+1} JSON 파싱 실패: {e}\n원문:\n{response.text[:500]}")
                return
        all_verdicts.extend(verdicts)

    print(f"\n전체 LLM 처리 시간: {total_elapsed:.1f}s\n")

    # 결과 분석
    verdict_map = {v["id"]: v for v in all_verdicts if isinstance(v.get("id"), str)}

    tp = tn = fp = fn = 0
    confidences = []
    # 패턴별 결과: A/B/C/D → (탐지 성공, 전체)
    pattern_stats: dict[str, list[int]] = {"A": [0, 0], "B": [0, 0], "C": [0, 0], "D": [0, 0]}

    print(f"{'ID':<22} {'기대':^8} {'판정':^8} {'정오':^5} {'conf':^6}  issues")
    print("-" * 80)

    for item_id, expected_valid in sorted(ground_truth.items()):
        v = verdict_map.get(item_id)
        if v is None:
            label = "valid" if expected_valid else "halluc"
            print(f"{item_id:<22} {label:^8} {'N/A':^8} {'?':^5} {'N/A':^6}  판정 없음")
            if not expected_valid:
                fn += 1
                htype = halluc_type_map.get(item_id, "?")
                if htype in pattern_stats:
                    pattern_stats[htype][1] += 1
            else:
                fn += 1
            continue

        predicted_valid = bool(v.get("is_valid", True))
        confidence = float(v.get("confidence", 0.5))
        issues = v.get("issues", [])
        confidences.append(confidence)

        correct = (predicted_valid == expected_valid)
        mark = "✅" if correct else "❌"

        if expected_valid and predicted_valid:          tp += 1
        elif not expected_valid and not predicted_valid: tn += 1
        elif not expected_valid and predicted_valid:     fp += 1
        else:                                            fn += 1

        # 패턴별 통계 (hallucinated 케이스만)
        if not expected_valid:
            htype = halluc_type_map.get(item_id, "?")
            if htype in pattern_stats:
                pattern_stats[htype][1] += 1
                if not predicted_valid:  # 탐지 성공
                    pattern_stats[htype][0] += 1

        issue_str = (issues[0][:35] + "…") if issues else ""
        label_e = "valid" if expected_valid else "halluc"
        label_p = "valid" if predicted_valid else "halluc"
        print(f"{item_id:<22} {label_e:^8} {label_p:^8} {mark:^5} {confidence:^6.2f}  {issue_str}")

    n = len(TEST_CASES)
    total = tp + tn + fp + fn
    accuracy  = (tp + tn) / total if total else 0
    halluc_recall = tn / (tn + fp) if (tn + fp) else 0   # halluc 중 탐지율
    valid_prec    = tp / (tp + fn) if (tp + fn) else 0   # valid 판정 정밀도
    avg_conf  = sum(confidences) / len(confidences) if confidences else 0

    print("\n" + "=" * 60)
    print("결과 요약")
    print("=" * 60)
    print(f"  총 건수:          {total} (valid {n}건, hallucinated {n}건)")
    print(f"  정확도:           {accuracy*100:.1f}%  ({tp+tn}/{total})")
    print(f"  Valid 판정 정확도: {tp}/{n} ({tp/n*100:.0f}%) — 올바른 피드백을 valid로 판정")
    print(f"  Halluc 탐지율:    {tn}/{n} ({tn/n*100:.0f}%) — 틀린 피드백 탐지")
    print(f"  FP (놓친 halluc):  {fp}건")
    print(f"  FN (오분류 valid): {fn}건")
    print(f"  평균 confidence:   {avg_conf:.2f}")
    print(f"  총 LLM 처리 시간:  {total_elapsed:.1f}s ({total_elapsed/total:.1f}s/건)")

    print("\n  [패턴별 탐지율]")
    pattern_desc = {
        "A": "A: wrong_cause  (엉뚱한 오류 원인 지적)",
        "B": "B: wrong_math   (수학적으로 틀린 교정)",
        "C": "C: wrong_concept (개념 자체가 틀림)",
        "D": "D: off_topic    (풀이와 무관한 지적)",
    }
    for ptype, (detected, total_p) in pattern_stats.items():
        if total_p == 0:
            continue
        rate = detected / total_p * 100
        bar = "█" * detected + "░" * (total_p - detected)
        print(f"    {pattern_desc[ptype]}: {detected}/{total_p} ({rate:.0f}%)  [{bar}]")

    print()
    if accuracy >= 0.80:
        print("✅ 할루시네이션 검증 정확도 80% 이상 — 실서비스 적용 가능 (ADR-026 기준 충족)")
    else:
        print("⚠️  정확도 80% 미만 — Claude API 전환 또는 프롬프트 튜닝 필요 (ADR-026 변경 조건 발동)")


if __name__ == "__main__":
    asyncio.run(run_hallucination_benchmark())
