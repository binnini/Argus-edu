import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from services.deterministic_grading import judge_final_answer


def test_judge_final_answer_correct():
    verdict = judge_final_answer("[최종 답] x = 3\n\n[풀이 과정]\nx=3", "x = 3")

    assert verdict.verdict == "correct"
    assert verdict.is_correct is True


def test_judge_final_answer_incorrect():
    verdict = judge_final_answer("[최종 답] x = 4", "x = 3")

    assert verdict.verdict == "incorrect"
    assert verdict.is_correct is False


def test_judge_final_answer_missing():
    verdict = judge_final_answer("풀이 과정만 있습니다.", "x = 3")

    assert verdict.verdict == "missing"
    assert verdict.is_correct is False
