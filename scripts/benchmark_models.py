#!/usr/bin/env python3
"""
benchmark_models.py — 채점+피드백 LLM 모델 벤치마크 (MLX 직접 실행)

사용법:
    # 단일 모델
    python scripts/benchmark_models.py --models gemma4:e4b

    # 여러 모델 비교
    python scripts/benchmark_models.py --models gemma4:e4b,qwen2.5:7b,exaone3.5:7.8b

    # HuggingFace 모델 ID 직접 지정
    python scripts/benchmark_models.py --models mlx-community/Qwen2.5-7B-Instruct-4bit

    # 문제 일부만 빠른 테스트
    python scripts/benchmark_models.py --models qwen2.5:7b --limit 5

    # Ollama HTTP API 사용 (MLX 대신)
    python scripts/benchmark_models.py --models qwen2.5:7b --ollama

    # 결과 CSV 저장
    python scripts/benchmark_models.py --models gemma4:e4b,qwen2.5:7b --output results.csv

    # 지원 모델 목록 확인
    python scripts/benchmark_models.py --list-models
"""

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


# ── MLX 모델 매핑 테이블 (tests/llm_benchmark_models.md 기준) ────────────
# key: Ollama 태그 / value: HuggingFace mlx-community 모델 ID

MLX_MODELS: dict[str, str] = {
    # ⚠️  gemma4 4-bit: PLE 레이어 양자화 버그로 쓰레기 출력 발생 (mlx-community/unsloth 모두 해당)
    #     8-bit 버전 사용 권장
    "gemma4:e4b":       "unsloth/gemma-4-E4B-it-MLX-8bit",
    "gemma4:e2b":       "unsloth/gemma-4-E2B-it-UD-MLX-4bit",  # unsloth UD 버전은 PLE 제외 양자화
    "mathstral:7b":     "mlx-community/mathstral-7B-v0.1-4bit",
    "qwen2.5:7b":       "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "deepseek-r1:7b":   "mlx-community/DeepSeek-R1-Distill-Qwen-7B-4bit",
    "deepseek-r1:14b":  "mlx-community/DeepSeek-R1-Distill-Qwen-14B-4bit",
    "exaone3.5:7.8b":   "mlx-community/EXAONE-3.5-7.8B-Instruct-4bit",
    "phi4:14b":         "mlx-community/phi-4-4bit",
    "qwen2.5:14b":      "mlx-community/Qwen2.5-14B-Instruct-4bit",
}

# DeepSeek-R1 계열: <think>...</think> 태그 제거 필요
DEEPSEEK_R1_PREFIXES = ("deepseek-r1", "DeepSeek-R1")


# ── 벤치마크 문제 (30개, 초등~고등 다양한 난이도) ────────────────────────

PROBLEMS = [
    # ── 초등 (E01~E08) ──────────────────────────────────────────────────
    {
        "id": "E01", "level": "초등3", "domain": "수와 연산",
        "content": "348 + 275를 계산하세요.",
        "answer": "623",
        "reference_solution": "1단계: 일의 자리 8+5=13, 받아올림 1\n2단계: 십의 자리 4+7+1=12, 받아올림 1\n3단계: 백의 자리 3+2+1=6\n답: 623",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "받아올림 처리", "score": 1},
            {"step": 2, "description": "최종 계산", "score": 1},
        ]},
        "student_answer": "348 + 275 = 613",
        "expected_score": 1,
    },
    {
        "id": "E02", "level": "초등4", "domain": "수와 연산",
        "content": "1/3 + 1/4를 계산하세요.",
        "answer": "7/12",
        "reference_solution": "1단계: 공통분모 12 구하기\n2단계: 1/3 = 4/12, 1/4 = 3/12\n3단계: 4/12 + 3/12 = 7/12",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "공통분모 구하기", "score": 1},
            {"step": 2, "description": "통분", "score": 1},
            {"step": 3, "description": "분수 덧셈", "score": 1},
        ]},
        "student_answer": "1/3 + 1/4 = 2/7",
        "expected_score": 0,
    },
    {
        "id": "E03", "level": "초등5", "domain": "측정",
        "content": "직사각형의 넓이를 구하세요. 가로: 8cm, 세로: 5cm",
        "answer": "40cm²",
        "reference_solution": "넓이 = 가로 × 세로 = 8 × 5 = 40(cm²)",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "공식 적용", "score": 1},
            {"step": 2, "description": "계산 및 단위", "score": 1},
        ]},
        "student_answer": "8 × 5 = 40cm²",
        "expected_score": 2,
    },
    {
        "id": "E04", "level": "초등6", "domain": "수와 연산",
        "content": "0.3 × 0.7을 계산하세요.",
        "answer": "0.21",
        "reference_solution": "0.3 × 0.7 = 3/10 × 7/10 = 21/100 = 0.21",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "소수 곱셈 원리", "score": 1},
            {"step": 2, "description": "소수점 위치", "score": 1},
        ]},
        "student_answer": "0.3 × 0.7 = 2.1",
        "expected_score": 1,
    },
    {
        "id": "E05", "level": "초등5", "domain": "자료와 가능성",
        "content": "주머니에 빨간 공 3개, 파란 공 2개가 있습니다. 무작위로 1개를 꺼낼 때 빨간 공이 나올 확률을 구하세요.",
        "answer": "3/5",
        "reference_solution": "전체 공 수: 3+2=5\n빨간 공이 나올 확률: 3/5",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "전체 경우의 수", "score": 1},
            {"step": 2, "description": "확률 계산", "score": 1},
        ]},
        "student_answer": "전체 5개 중 빨간 공 3개이므로 확률은 3/5입니다.",
        "expected_score": 2,
    },
    {
        "id": "E06", "level": "초등4", "domain": "도형",
        "content": "삼각형의 세 각의 합은 몇 도인가요? 두 각이 각각 50°, 70°일 때 나머지 한 각을 구하세요.",
        "answer": "60°",
        "reference_solution": "삼각형 내각의 합 = 180°\n나머지 각 = 180° - 50° - 70° = 60°",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "내각의 합 180° 적용", "score": 1},
            {"step": 2, "description": "나머지 각 계산", "score": 1},
        ]},
        "student_answer": "180 - 50 - 70 = 60°",
        "expected_score": 2,
    },
    {
        "id": "E07", "level": "초등3", "domain": "수와 연산",
        "content": "72 ÷ 8을 계산하세요.",
        "answer": "9",
        "reference_solution": "8 × 9 = 72이므로 72 ÷ 8 = 9",
        "rubric": {"total_score": 1, "steps": [
            {"step": 1, "description": "나눗셈 계산", "score": 1},
        ]},
        "student_answer": "72 ÷ 8 = 8",
        "expected_score": 0,
    },
    {
        "id": "E08", "level": "초등6", "domain": "수와 연산",
        "content": "(-3) + 5를 계산하세요.",
        "answer": "2",
        "reference_solution": "절댓값이 큰 양수 5에서 3을 빼면 5-3=2 (양수)",
        "rubric": {"total_score": 1, "steps": [
            {"step": 1, "description": "정수 덧셈", "score": 1},
        ]},
        "student_answer": "(-3) + 5 = -8",
        "expected_score": 0,
    },

    # ── 중학교 (M01~M10) ────────────────────────────────────────────────
    {
        "id": "M01", "level": "중1", "domain": "방정식",
        "content": "일차방정식 2x + 3 = 11을 풀어라.",
        "answer": "x = 4",
        "reference_solution": "2x = 11 - 3 = 8\nx = 4",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "이항", "score": 1},
            {"step": 2, "description": "풀이", "score": 1},
        ]},
        "student_answer": "2x = 8이므로 x = 4",
        "expected_score": 2,
    },
    {
        "id": "M02", "level": "중1", "domain": "함수",
        "content": "y = 2x - 1에서 x = 3일 때 y의 값을 구하라.",
        "answer": "5",
        "reference_solution": "y = 2(3) - 1 = 6 - 1 = 5",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "대입", "score": 1},
            {"step": 2, "description": "계산", "score": 1},
        ]},
        "student_answer": "y = 2×3 - 1 = 6 - 1 = 5",
        "expected_score": 2,
    },
    {
        "id": "M03", "level": "중2", "domain": "도형",
        "content": "직각삼각형에서 빗변의 길이가 5, 한 변의 길이가 3일 때 나머지 변의 길이를 구하라.",
        "answer": "4",
        "reference_solution": "피타고라스 정리: a² + b² = c²\n3² + b² = 5²\nb² = 25 - 9 = 16\nb = 4",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "피타고라스 정리 적용", "score": 1},
            {"step": 2, "description": "식 계산", "score": 1},
            {"step": 3, "description": "답 도출", "score": 1},
        ]},
        "student_answer": "3² + b² = 5²이면 9 + b² = 25, b² = 16, b = 4",
        "expected_score": 3,
    },
    {
        "id": "M04", "level": "중2", "domain": "방정식",
        "content": "연립방정식을 풀어라: x + y = 5, 2x - y = 1",
        "answer": "x = 2, y = 3",
        "reference_solution": "두 식을 더하면 3x = 6, x = 2\nx = 2를 첫 번째 식에 대입: y = 3",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "소거법 또는 대입법", "score": 1},
            {"step": 2, "description": "x 풀이", "score": 1},
            {"step": 3, "description": "y 풀이", "score": 1},
        ]},
        "student_answer": "첫 번째 식에서 y = 5-x를 두 번째에 대입\n2x-(5-x)=1, 3x=6, x=2, y=3",
        "expected_score": 3,
    },
    {
        "id": "M05", "level": "중3", "domain": "이차방정식",
        "content": "이차방정식 x² - 5x + 6 = 0을 풀어라.",
        "answer": "x = 2 또는 x = 3",
        "reference_solution": "(x-2)(x-3) = 0으로 인수분해\nx = 2 또는 x = 3",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "인수분해 또는 근의 공식", "score": 1},
            {"step": 2, "description": "인수분해 결과", "score": 1},
            {"step": 3, "description": "해 도출", "score": 1},
        ]},
        "student_answer": "x² - 5x + 6 = (x-2)(x-3) = 0\nx = 2 또는 x = 4",
        "expected_score": 2,
    },
    {
        "id": "M06", "level": "중1", "domain": "통계",
        "content": "자료 3, 7, 5, 9, 1의 평균과 중앙값을 구하라.",
        "answer": "평균: 5, 중앙값: 5",
        "reference_solution": "평균: (3+7+5+9+1)/5 = 25/5 = 5\n정렬: 1,3,5,7,9 → 중앙값 = 5",
        "rubric": {"total_score": 4, "steps": [
            {"step": 1, "description": "합 계산", "score": 1},
            {"step": 2, "description": "평균 계산", "score": 1},
            {"step": 3, "description": "자료 정렬", "score": 1},
            {"step": 4, "description": "중앙값 도출", "score": 1},
        ]},
        "student_answer": "평균: 25÷5=5\n중앙값: 정렬하면 1,3,5,7,9이므로 중앙값은 5",
        "expected_score": 4,
    },
    {
        "id": "M07", "level": "중3", "domain": "함수",
        "content": "함수 f(x) = x² - 4의 x절편을 구하라.",
        "answer": "x = -2, x = 2",
        "reference_solution": "x² - 4 = 0\n(x+2)(x-2) = 0\nx = ±2",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "f(x)=0 설정", "score": 1},
            {"step": 2, "description": "x 풀이", "score": 1},
        ]},
        "student_answer": "x² = 4이므로 x = 2만 있다",
        "expected_score": 1,
    },
    {
        "id": "M08", "level": "중2", "domain": "도형",
        "content": "원의 반지름이 5cm일 때 넓이를 구하라. (π 사용)",
        "answer": "25π cm²",
        "reference_solution": "넓이 = πr² = π × 5² = 25π(cm²)",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "공식 적용", "score": 1},
            {"step": 2, "description": "계산 및 단위", "score": 1},
        ]},
        "student_answer": "πr² = π × 25 = 25π cm²",
        "expected_score": 2,
    },
    {
        "id": "M09", "level": "중3", "domain": "확률",
        "content": "동전을 두 번 던질 때 두 번 모두 앞면이 나올 확률을 구하라.",
        "answer": "1/4",
        "reference_solution": "전체 경우의 수: {앞앞, 앞뒤, 뒤앞, 뒤뒤} = 4\n두 번 모두 앞: 1가지\n확률 = 1/4",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "전체 경우의 수", "score": 1},
            {"step": 2, "description": "사건의 경우의 수", "score": 1},
            {"step": 3, "description": "확률 계산", "score": 1},
        ]},
        "student_answer": "각각 1/2이므로 1/2 × 1/2 = 1/4",
        "expected_score": 3,
    },
    {
        "id": "M10", "level": "중1", "domain": "수와 연산",
        "content": "(-2)³을 계산하라.",
        "answer": "-8",
        "reference_solution": "(-2)³ = (-2)×(-2)×(-2) = 4×(-2) = -8",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "거듭제곱 전개", "score": 1},
            {"step": 2, "description": "부호 결정", "score": 1},
        ]},
        "student_answer": "(-2)³ = -2³ = -8",
        "expected_score": 2,
    },

    # ── 고등학교 (H01~H12) ───────────────────────────────────────────────
    {
        "id": "H01", "level": "고1", "domain": "지수·로그",
        "content": "log₂8의 값을 구하라.",
        "answer": "3",
        "reference_solution": "log₂8 = log₂2³ = 3",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "8 = 2³ 변환", "score": 1},
            {"step": 2, "description": "로그 계산", "score": 1},
        ]},
        "student_answer": "2³ = 8이므로 log₂8 = 3",
        "expected_score": 2,
    },
    {
        "id": "H02", "level": "고1", "domain": "이차함수",
        "content": "이차함수 f(x) = x² - 4x + 3의 꼭짓점을 구하라.",
        "answer": "(2, -1)",
        "reference_solution": "f(x) = (x-2)² - 4 + 3 = (x-2)² - 1\n꼭짓점: (2, -1)",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "완전제곱식 변환", "score": 1},
            {"step": 2, "description": "꼭짓점 x좌표", "score": 1},
            {"step": 3, "description": "꼭짓점 y좌표", "score": 1},
        ]},
        "student_answer": "x² - 4x + 3 = (x-2)² - 1이므로 꼭짓점은 (2, 1)",
        "expected_score": 2,
    },
    {
        "id": "H03", "level": "고2", "domain": "미분",
        "content": "f(x) = 3x² + 2x - 1의 도함수 f'(x)를 구하라.",
        "answer": "f'(x) = 6x + 2",
        "reference_solution": "f'(x) = 3·2x + 2·1 = 6x + 2",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "거듭제곱 미분", "score": 1},
            {"step": 2, "description": "상수 미분", "score": 1},
        ]},
        "student_answer": "f'(x) = 6x + 2",
        "expected_score": 2,
    },
    {
        "id": "H04", "level": "고2", "domain": "미분",
        "content": "f(x) = x³ - 3x의 극값을 구하라.",
        "answer": "극대: x=-1에서 f(-1)=2, 극소: x=1에서 f(1)=-2",
        "reference_solution": "f'(x) = 3x² - 3 = 3(x-1)(x+1)\nf'(x)=0: x=-1 또는 x=1\n증감표로 극대(2), 극소(-2) 확인",
        "rubric": {"total_score": 4, "steps": [
            {"step": 1, "description": "도함수 계산", "score": 1},
            {"step": 2, "description": "임계점 도출", "score": 1},
            {"step": 3, "description": "극대 계산", "score": 1},
            {"step": 4, "description": "극소 계산", "score": 1},
        ]},
        "student_answer": "f'(x)=3x²-3=0이면 x²=1, x=±1\nf(-1)=2(극대), f(1)=-2(극소)",
        "expected_score": 4,
    },
    {
        "id": "H05", "level": "고2", "domain": "적분",
        "content": "∫(2x + 3)dx를 계산하라.",
        "answer": "x² + 3x + C",
        "reference_solution": "∫(2x + 3)dx = x² + 3x + C",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "2x 적분", "score": 1},
            {"step": 2, "description": "3 적분", "score": 1},
            {"step": 3, "description": "적분상수 C", "score": 1},
        ]},
        "student_answer": "∫(2x+3)dx = x² + 3x",
        "expected_score": 2,
    },
    {
        "id": "H06", "level": "고2", "domain": "적분",
        "content": "∫₀² (3x²)dx 를 계산하라.",
        "answer": "8",
        "reference_solution": "[x³]₀² = 2³ - 0³ = 8",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "부정적분", "score": 1},
            {"step": 2, "description": "상한 대입", "score": 1},
            {"step": 3, "description": "하한 빼기", "score": 1},
        ]},
        "student_answer": "∫₀²3x²dx = [x³]₀² = 8 - 0 = 8",
        "expected_score": 3,
    },
    {
        "id": "H07", "level": "고1", "domain": "수열",
        "content": "등차수열의 첫째항이 2, 공차가 3일 때 10번째 항을 구하라.",
        "answer": "29",
        "reference_solution": "aₙ = a₁ + (n-1)d = 2 + (10-1)×3 = 2 + 27 = 29",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "일반항 공식 적용", "score": 1},
            {"step": 2, "description": "계산", "score": 1},
        ]},
        "student_answer": "a₁₀ = 2 + 9×3 = 29",
        "expected_score": 2,
    },
    {
        "id": "H08", "level": "고1", "domain": "수열",
        "content": "등비수열 첫째항 3, 공비 2의 첫 5항의 합을 구하라.",
        "answer": "93",
        "reference_solution": "Sₙ = a(rⁿ-1)/(r-1) = 3(2⁵-1)/(2-1) = 3×31 = 93",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "등비수열 합 공식", "score": 1},
            {"step": 2, "description": "식 대입", "score": 1},
            {"step": 3, "description": "계산", "score": 1},
        ]},
        "student_answer": "S₅ = 3(2⁵-1)/(2-1) = 3×32/(1) = 96",
        "expected_score": 2,
    },
    {
        "id": "H09", "level": "고3", "domain": "확률",
        "content": "서로 다른 5개에서 3개를 뽑는 조합의 수 ₅C₃을 구하라.",
        "answer": "10",
        "reference_solution": "₅C₃ = 5!/(3!2!) = (5×4)/(2×1) = 10",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "조합 공식 적용", "score": 1},
            {"step": 2, "description": "계산", "score": 1},
        ]},
        "student_answer": "₅C₃ = 5×4×3/(3×2×1) = 10",
        "expected_score": 2,
    },
    {
        "id": "H10", "level": "고3", "domain": "미분",
        "content": "함수 f(x) = x³ - 3x² + 1이 [0, 3]에서 최솟값을 구하라.",
        "answer": "f(2) = -3",
        "reference_solution": "f'(x) = 3x² - 6x = 3x(x-2)\nf'(x)=0: x=0, x=2\nf(0)=1, f(2)=-3, f(3)=1\n최솟값: -3",
        "rubric": {"total_score": 4, "steps": [
            {"step": 1, "description": "도함수 계산", "score": 1},
            {"step": 2, "description": "임계점 도출", "score": 1},
            {"step": 3, "description": "구간 양끝 + 임계점 함수값 계산", "score": 1},
            {"step": 4, "description": "최솟값 결론", "score": 1},
        ]},
        "student_answer": "f'(x)=3x²-6x=0에서 x=0,2\nf(0)=1, f(2)=8-12+1=-3, f(3)=1\n최솟값=-3",
        "expected_score": 4,
    },
    {
        "id": "H11", "level": "고2", "domain": "삼각함수",
        "content": "sin30° + cos60°의 값을 구하라.",
        "answer": "1",
        "reference_solution": "sin30° = 1/2, cos60° = 1/2\n따라서 1/2 + 1/2 = 1",
        "rubric": {"total_score": 2, "steps": [
            {"step": 1, "description": "특수각 값", "score": 1},
            {"step": 2, "description": "덧셈", "score": 1},
        ]},
        "student_answer": "sin30° = 1/2, cos60° = 1/2이므로 합은 1",
        "expected_score": 2,
    },
    {
        "id": "H12", "level": "고3", "domain": "미적분",
        "content": "lim(x→2) (x²-4)/(x-2) 를 구하라.",
        "answer": "4",
        "reference_solution": "(x²-4)/(x-2) = (x+2)(x-2)/(x-2) = x+2\nlim(x→2)(x+2) = 4",
        "rubric": {"total_score": 3, "steps": [
            {"step": 1, "description": "분자 인수분해", "score": 1},
            {"step": 2, "description": "약분", "score": 1},
            {"step": 3, "description": "극한값 계산", "score": 1},
        ]},
        "student_answer": "(x²-4)을 (x+2)(x-2)로 인수분해하면 약분되어 x+2\nx→2 대입: 4",
        "expected_score": 3,
    },
]


# ── 프롬프트 ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
당신은 한국 수학 채점 및 개인화 피드백 전문가입니다.
학생 답변을 루브릭 기준으로 단계별 채점하고, 학생의 오류를 분석한 개인화 피드백을 작성하세요.
반드시 아래 JSON 형식으로만 응답하세요. 수학적 사실에 근거하지 않는 내용은 절대 포함하지 마세요."""

USER_TEMPLATE = """\
[문제]
{problem_content}

[정답]
{answer}

[참조 풀이]
{reference_solution}

[채점 루브릭]
{rubric_json}

[학생 답변]
{student_answer}

위 루브릭에 따라 채점하고 개인화 피드백을 작성하세요.

{{
  "grading": {{
    "total_score": <총점, 정수>,
    "steps": [{{"step": 1, "earned": <정수>, "max": <정수>, "reason": "<1~2문장>"}}],
    "overall_comment": "<총평>"
  }},
  "feedback": {{
    "student_mistakes": [{{"step": <정수 or 0>, "description": "<설명>"}}],
    "correct_approach": [{{"step": <정수>, "title": "<제목>", "content": "<내용>"}}],
    "key_concept": "<핵심 개념 1~2문장>"
  }}
}}

student_mistakes가 없으면 [] 로 응답하세요."""


# ── 결과 클래스 ───────────────────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    problem_id: str
    level: str
    domain: str
    model: str
    elapsed_sec: float
    ai_score: Optional[int]
    expected_score: int
    total_score: int
    score_correct: bool
    key_concept: str
    mistake_count: int
    error: str = ""
    raw_response: str = field(default="", repr=False)


# ── JSON 파싱 ─────────────────────────────────────────────────────────────

def strip_think_tags(text: str) -> str:
    """DeepSeek-R1 계열의 <think>...</think> 추론 블록 제거."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def parse_response(raw: str, is_deepseek: bool = False) -> dict:
    text = raw.strip()
    if is_deepseek:
        text = strip_think_tags(text)
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)
        return json.loads(text)


# ── MLX 추론 ──────────────────────────────────────────────────────────────

def resolve_model_id(name: str) -> str:
    """Ollama 태그 → HF 모델 ID 변환. 이미 HF ID면 그대로 반환."""
    return MLX_MODELS.get(name, name)


def is_deepseek_r1(name: str) -> bool:
    return any(name.startswith(p) for p in DEEPSEEK_R1_PREFIXES)


def build_prompt_mlx(tokenizer, problem: dict) -> str:
    user_content = USER_TEMPLATE.format(
        problem_content=problem["content"],
        answer=problem["answer"],
        reference_solution=problem["reference_solution"],
        rubric_json=json.dumps(problem["rubric"], ensure_ascii=False),
        student_answer=problem["student_answer"],
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    # chat_template이 실제로 설정된 경우에만 apply_chat_template 사용
    chat_template = getattr(tokenizer, "chat_template", None)
    if chat_template:
        try:
            return tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            pass
    # fallback: Instruct 형식 수동 조합
    return f"<s>[INST] {SYSTEM_PROMPT}\n\n{user_content} [/INST]"


def run_mlx_benchmark(
    model_name: str,
    problems: list[dict],
    max_tokens: int = 2048,
    temp: float = 0.7,
    debug: bool = False,
) -> list[BenchmarkResult]:
    try:
        from mlx_lm import load, generate
        import mlx.core as mx
    except ImportError:
        print("mlx-lm이 필요합니다: pip install mlx-lm")
        sys.exit(1)

    hf_id = resolve_model_id(model_name)
    deepseek = is_deepseek_r1(model_name) or is_deepseek_r1(hf_id)

    print(f"  모델 로딩: {hf_id}")
    load_start = time.perf_counter()
    model, tokenizer = load(hf_id)
    load_sec = time.perf_counter() - load_start
    print(f"  로딩 완료: {load_sec:.1f}초\n")

    results: list[BenchmarkResult] = []

    for i, problem in enumerate(problems, 1):
        prompt = build_prompt_mlx(tokenizer, problem)
        t0 = time.perf_counter()
        error = ""
        ai_score = None
        key_concept = ""
        mistake_count = 0
        raw = ""

        try:
            # mlx-lm 버전에 따라 temperature 파라미터 방식이 다름
            # 신버전: sampler 객체로 전달 / 구버전: temp= 직접 전달
            try:
                from mlx_lm.sample_utils import make_sampler
                sampler = make_sampler(temp=temp)
                raw = generate(
                    model, tokenizer,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    sampler=sampler,
                    verbose=False,
                )
            except (ImportError, TypeError):
                raw = generate(
                    model, tokenizer,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    verbose=False,
                )
            if debug:
                print(f"\n  [DEBUG raw ({problem['id']})]:\n{raw[:600]}\n{'─'*40}")
            parsed = parse_response(raw, is_deepseek=deepseek)
            ai_score = int(parsed["grading"]["total_score"])
            key_concept = parsed["feedback"].get("key_concept", "")[:60]
            mistake_count = len(parsed["feedback"].get("student_mistakes", []))
        except Exception as e:
            raw_preview = raw[:120].replace("\n", " ") if raw else "<empty>"
            error = f"{str(e)[:80]} | raw: {raw_preview}"

        elapsed = round(time.perf_counter() - t0, 2)
        r = BenchmarkResult(
            problem_id=problem["id"],
            level=problem["level"],
            domain=problem["domain"],
            model=model_name,
            elapsed_sec=elapsed,
            ai_score=ai_score,
            expected_score=problem["expected_score"],
            total_score=problem["rubric"]["total_score"],
            score_correct=(ai_score == problem["expected_score"]) if ai_score is not None else False,
            key_concept=key_concept,
            mistake_count=mistake_count,
            error=error,
            raw_response=raw,
        )
        results.append(r)
        print_result(r, i, len(problems))

    # 메모리 해제
    del model, tokenizer
    try:
        import mlx.core as mx
        mx.clear_cache()
    except Exception:
        pass

    return results


# ── Ollama 폴백 ───────────────────────────────────────────────────────────

def run_ollama_benchmark(
    model_name: str,
    problems: list[dict],
    base_url: str,
    timeout: int,
) -> list[BenchmarkResult]:
    try:
        from openai import OpenAI
    except ImportError:
        print("openai 패키지가 필요합니다: pip install openai")
        sys.exit(1)

    deepseek = is_deepseek_r1(model_name)
    client = OpenAI(base_url=f"{base_url}/v1", api_key="ollama")
    results: list[BenchmarkResult] = []

    for i, problem in enumerate(problems, 1):
        user_content = USER_TEMPLATE.format(
            problem_content=problem["content"],
            answer=problem["answer"],
            reference_solution=problem["reference_solution"],
            rubric_json=json.dumps(problem["rubric"], ensure_ascii=False),
            student_answer=problem["student_answer"],
        )
        t0 = time.perf_counter()
        error = ""
        ai_score = None
        key_concept = ""
        mistake_count = 0
        raw = ""

        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=2048,
                temperature=0.7,
                timeout=timeout,
            )
            raw = resp.choices[0].message.content or ""
            parsed = parse_response(raw, is_deepseek=deepseek)
            ai_score = int(parsed["grading"]["total_score"])
            key_concept = parsed["feedback"].get("key_concept", "")[:60]
            mistake_count = len(parsed["feedback"].get("student_mistakes", []))
        except Exception as e:
            error = str(e)[:120]

        elapsed = round(time.perf_counter() - t0, 2)
        r = BenchmarkResult(
            problem_id=problem["id"],
            level=problem["level"],
            domain=problem["domain"],
            model=model_name,
            elapsed_sec=elapsed,
            ai_score=ai_score,
            expected_score=problem["expected_score"],
            total_score=problem["rubric"]["total_score"],
            score_correct=(ai_score == problem["expected_score"]) if ai_score is not None else False,
            key_concept=key_concept,
            mistake_count=mistake_count,
            error=error,
            raw_response=raw,
        )
        results.append(r)
        print_result(r, i, len(problems))

    return results


# ── 출력 ──────────────────────────────────────────────────────────────────

def print_result(r: BenchmarkResult, idx: int, total: int):
    status = "✅" if r.score_correct else ("💥" if r.error else "❌")
    score_str = f"{r.ai_score}/{r.total_score}" if r.ai_score is not None else "ERR"
    exp_str = f"{r.expected_score}/{r.total_score}"
    print(
        f"  [{idx:2d}/{total}] {status} {r.problem_id} ({r.level}/{r.domain})"
        f" | {r.elapsed_sec:6.1f}s | AI:{score_str} 예상:{exp_str}"
        f" | 오류{r.mistake_count}개 | {r.key_concept[:38]}"
        + (f"\n       💥 {r.error}" if r.error else "")
    )


def print_summary(results: list[BenchmarkResult], model: str):
    valid = [r for r in results if r.ai_score is not None]
    errors = [r for r in results if r.error]
    correct = [r for r in valid if r.score_correct]

    print(f"\n{'='*72}")
    print(f"모델: {model}")
    print(f"{'='*72}")
    print(f"  총 문제: {len(results)}개  |  성공: {len(valid)}개  |  오류: {len(errors)}개")
    if valid:
        avg_time = sum(r.elapsed_sec for r in valid) / len(valid)
        total_time = sum(r.elapsed_sec for r in results)
        acc = 100 * len(correct) / len(valid)
        print(f"  채점 정확도: {len(correct)}/{len(valid)} ({acc:.1f}%)")
        print(f"  평균 소요시간: {avg_time:.1f}초  |  전체: {total_time:.0f}초")

        by_level: dict[str, list] = {}
        for r in valid:
            key = r.level[:2]
            by_level.setdefault(key, []).append(r)
        for lvl, rs in sorted(by_level.items()):
            ok = sum(1 for r in rs if r.score_correct)
            avg = sum(r.elapsed_sec for r in rs) / len(rs)
            print(f"    {lvl}: {ok}/{len(rs)} 정답, 평균 {avg:.1f}초")
    print(f"{'='*72}\n")


def print_comparison(all_results: list[BenchmarkResult]):
    """모델 간 최종 비교표 출력."""
    by_model: dict[str, list] = {}
    for r in all_results:
        by_model.setdefault(r.model, []).append(r)

    if len(by_model) < 2:
        return

    print(f"\n{'━'*72}")
    print("모델 비교 요약")
    print(f"{'━'*72}")
    header = f"  {'모델':<30} {'정확도':>8} {'평균(초)':>9} {'오류':>5}"
    print(header)
    print(f"  {'-'*62}")

    rows = []
    for model, results in by_model.items():
        valid = [r for r in results if r.ai_score is not None]
        if not valid:
            rows.append((model, 0.0, 9999.0, len(results)))
            continue
        correct = sum(1 for r in valid if r.score_correct)
        acc = 100 * correct / len(valid)
        avg = sum(r.elapsed_sec for r in valid) / len(valid)
        err = sum(1 for r in results if r.error)
        rows.append((model, acc, avg, err))

    for model, acc, avg, err in sorted(rows, key=lambda x: -x[1]):
        print(f"  {model:<30} {acc:>7.1f}% {avg:>8.1f}s {err:>5}개")
    print(f"{'━'*72}\n")


def save_csv(results: list[BenchmarkResult], path: str):
    if not results:
        return
    fieldnames = [f for f in asdict(results[0]).keys() if f != "raw_response"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            d = asdict(r)
            d.pop("raw_response", None)
            writer.writerow(d)
    print(f"CSV 저장: {path}")


# ── 메인 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Argus LLM 채점+피드백 벤치마크")
    parser.add_argument(
        "--models", default="qwen2.5:7b",
        help="콤마 구분 모델 목록. Ollama 태그 또는 HF 모델 ID 사용 가능.\n"
             "예: gemma4:e4b,qwen2.5:7b,exaone3.5:7.8b",
    )
    parser.add_argument(
        "--ollama", action="store_true",
        help="MLX 대신 Ollama HTTP API 사용",
    )
    parser.add_argument(
        "--base-url", default="http://localhost:11434",
        help="Ollama 서버 주소 (--ollama 사용 시, 기본: http://localhost:11434)",
    )
    parser.add_argument(
        "--timeout", type=int, default=180,
        help="Ollama 호출 타임아웃 초 (기본: 180)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="테스트할 문제 수 제한 (0=전체 30개)",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=2048,
        help="최대 생성 토큰 수 (기본: 2048)",
    )
    parser.add_argument(
        "--temp", type=float, default=0.7,
        help="샘플링 온도 (기본: 0.7)",
    )
    parser.add_argument(
        "--output", default="",
        help="CSV 저장 경로 (기본: benchmark_YYYYMMDD_HHMMSS.csv)",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="각 문제의 원본 LLM 응답 출력 (파싱 오류 디버깅용)",
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="지원 MLX 모델 목록 출력 후 종료",
    )
    args = parser.parse_args()

    if args.list_models:
        print("\n지원 모델 (MLX_MODELS 매핑 테이블):")
        print(f"  {'Ollama 태그':<25} {'HuggingFace 모델 ID'}")
        print(f"  {'-'*65}")
        for tag, hf_id in MLX_MODELS.items():
            print(f"  {tag:<25} {hf_id}")
        print()
        return

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    problems = PROBLEMS[: args.limit] if args.limit else PROBLEMS
    mode = "Ollama" if args.ollama else "MLX"

    print(f"\nArgus 모델 벤치마크 ({mode}) — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"문제: {len(problems)}개  |  모델: {', '.join(models)}\n")

    all_results: list[BenchmarkResult] = []

    for model in models:
        print(f"── 모델: {model} {'─'*50}")
        if args.ollama:
            results = run_ollama_benchmark(model, problems, args.base_url, args.timeout)
        else:
            results = run_mlx_benchmark(model, problems, args.max_tokens, args.temp, debug=args.debug)
        all_results.extend(results)
        print_summary(results, model)

    print_comparison(all_results)

    output_path = args.output or f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    save_csv(all_results, output_path)


if __name__ == "__main__":
    main()
