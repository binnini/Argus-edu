const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface Problem {
  id: number;
  title: string;
  content: string;
  domain: string;
  difficulty: number;
  total_score: number;
}

export interface SubmissionRequest {
  problem_id: number;
  student_answer: string;
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
  explanation: string | null;
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

export async function submitAnswer(
  payload: SubmissionRequest
): Promise<SubmissionCreateResponse> {
  const res = await fetch(`${API_BASE}/submissions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `제출 실패: ${res.status}`);
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
