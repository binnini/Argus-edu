"""Deterministic final-answer grading for pass/fail MVP scoring."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerVerdict:
    verdict: str  # correct | incorrect | missing | uncertain
    student_values: list[str]
    answer_values: list[str]
    reason: str

    @property
    def is_correct(self) -> bool:
        return self.verdict == "correct"


def _extract_final_answer(student_answer: str) -> str | None:
    match = re.search(r"\[최종 답\]\s*(.+?)(?:\n|$)", student_answer)
    if not match:
        return None
    final = match.group(1).strip()
    return final or None


def _extract_values(text: str) -> list[str]:
    cleaned = re.sub(r"\$", "", text)
    cleaned = re.sub(r"\\[a-zA-Z]+", "", cleaned)
    cleaned = re.sub(r"[{}]", "", cleaned)
    values = re.findall(r"-?\d+(?:\.\d+)?", cleaned)
    return sorted(set(values))


def judge_final_answer(student_answer: str, problem_answer: str) -> AnswerVerdict:
    """Return a structured final-answer verdict without using an LLM."""
    final = _extract_final_answer(student_answer)
    if final is None:
        return AnswerVerdict(
            verdict="missing",
            student_values=[],
            answer_values=_extract_values(problem_answer),
            reason="학생 최종 답이 입력되지 않았습니다.",
        )

    student_values = _extract_values(final)
    answer_values = _extract_values(problem_answer)

    if not student_values:
        return AnswerVerdict(
            verdict="uncertain",
            student_values=[],
            answer_values=answer_values,
            reason="학생 최종 답에서 비교 가능한 값을 추출하지 못했습니다.",
        )
    if not answer_values:
        return AnswerVerdict(
            verdict="uncertain",
            student_values=student_values,
            answer_values=[],
            reason="문제 정답에서 비교 가능한 값을 추출하지 못했습니다.",
        )

    student_set = set(student_values)
    answer_set = set(answer_values)
    if student_set == answer_set or student_set.issubset(answer_set):
        return AnswerVerdict(
            verdict="correct",
            student_values=student_values,
            answer_values=answer_values,
            reason="학생 최종 답이 정답 값과 일치합니다.",
        )

    return AnswerVerdict(
        verdict="incorrect",
        student_values=student_values,
        answer_values=answer_values,
        reason="학생 최종 답이 정답 값과 일치하지 않습니다.",
    )
