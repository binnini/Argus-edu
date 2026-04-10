const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface Problem {
  id: number;
  title: string;
  content: string;
  domain: string;
  difficulty: number;
  total_score: number;
}

export interface FeedbackMistake {
  step: number;
  description: string;
}

export interface FeedbackStep {
  step: number;
  title: string;
  content: string;
}

export interface Feedback {
  student_mistakes: FeedbackMistake[];
  correct_approach: FeedbackStep[];
  key_concept: string;
}

export interface SubmissionCreateResponse {
  submission_id: number;
  status: string;
  message: string;
}

export interface SubmissionStatusResponse {
  submission_id: number;
  status: string;
  score: number | null;
  score_visible: boolean;
  feedback: Feedback | null;  // 교사 승인 후에만 노출
  teacher_approved: boolean;
  message: string | null;
}

export async function getProblems(): Promise<Problem[]> {
  const res = await fetch(`${API_BASE}/problems`);
  if (!res.ok) throw new Error(`문제 목록 조회 실패: ${res.status}`);
  const data = await res.json();
  return data.problems;
}

export async function getProblem(problemId: number): Promise<Problem> {
  const res = await fetch(`${API_BASE}/problems/${problemId}`);
  if (!res.ok) throw new Error(`문제 조회 실패: ${res.status}`);
  return res.json();
}

export async function submitAnswerText(
  problemId: number,
  studentAnswer: string,
  studentName: string,
  studentId?: string,
): Promise<SubmissionCreateResponse> {
  const res = await fetch(`${API_BASE}/submissions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      problem_id: problemId,
      student_answer: studentAnswer,
      student_name: studentName,
      student_id: studentId ?? null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `제출 실패: ${res.status}`);
  }
  return res.json();
}

export async function submitAnswerImage(
  problemId: number,
  imageFile: File,
  studentName: string,
  studentId?: string,
): Promise<SubmissionCreateResponse> {
  const formData = new FormData();
  formData.append("problem_id", String(problemId));
  formData.append("image", imageFile);
  formData.append("student_name", studentName);
  if (studentId) {
    formData.append("student_id", studentId);
  }

  const res = await fetch(`${API_BASE}/submissions/image`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `이미지 제출 실패: ${res.status}`);
  }
  return res.json();
}

export async function getSubmissionStatus(
  submissionId: number
): Promise<SubmissionStatusResponse> {
  const res = await fetch(`${API_BASE}/submissions/${submissionId}`);
  if (!res.ok) throw new Error(`채점 결과 조회 실패: ${res.status}`);
  return res.json();
}
