"""Combined grading and feedback prompt templates."""

COMBINED_SYSTEM_PROMPT = """\
당신은 한국 수학 채점 및 개인화 피드백 전문가입니다.
학생 답변을 루브릭 기준으로 단계별 채점하고, 학생의 오류를 분석한 개인화 피드백을 작성하세요.
반드시 아래 JSON 형식으로만 응답하세요. 수학적 사실에 근거하지 않는 내용은 절대 포함하지 마세요."""

COMBINED_USER_TEMPLATE = """\
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

[최종 답 정오 판별 — 시스템 자동 검증 결과]
{answer_verdict}

채점 원칙:
1. 위 "최종 답 정오 판별"은 학생의 [최종 답]과 정답 숫자를 직접 비교한 확정적 사실입니다.
   오답으로 판별된 경우, 최종 값을 구하는 마지막 단계는 반드시 0점으로 채점하세요.
2. 중간 풀이 과정은 각 단계의 계산이 수학적으로 올바른지 직접 검증하여 채점하세요.
3. grading.steps의 earned 합계가 반드시 grading.total_score와 같아야 합니다.

위 루브릭에 따라 채점하고, 학생의 오류를 분석한 개인화 피드백을 작성하세요.
반드시 아래 JSON 형식으로만 응답하세요.

{{
  "grading": {{
    "total_score": <총점, 정수>,
    "steps": [
      {{
        "step": <단계 번호>,
        "earned": <획득 점수, 정수>,
        "max": <최대 점수, 정수>,
        "reason": "<판단 근거, 1~2문장>"
      }}
    ],
    "overall_comment": "<총평, 1~2문장>"
  }},
  "feedback": {{
    "student_mistakes": [
      {{
        "step": <틀린 단계 번호, 없으면 0>,
        "description": "<학생이 어디서 어떻게 틀렸는지 구체적 설명>"
      }}
    ],
    "correct_approach": [
      {{
        "step": <단계 번호>,
        "title": "<단계 제목>",
        "content": "<이 학생이 이해해야 할 내용>"
      }}
    ],
    "key_concept": "<이 문제에서 학생이 놓친 핵심 개념, 1~2문장>"
  }}
}}

student_mistakes가 없으면 빈 배열 []로 응답하세요."""
