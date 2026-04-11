const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface RubricStep {
  step: number;
  description: string;
  score: number;
}

export interface RubricSchema {
  total_score: number;
  steps: RubricStep[];
}

export interface ProblemCreate {
  title: string;
  content: string;
  answer: string;
  reference_solution: string;
  rubric: RubricSchema;
  domain?: string;
  difficulty?: number;
}

export interface TeacherProblemItem {
  id: number;
  title: string;
  content: string;
  answer: string;
  reference_solution: string;
  rubric: Record<string, unknown>;
  domain: string;
  difficulty: number;
  submission_count: number;
  created_at: string;
}

export async function getProblems(): Promise<TeacherProblemItem[]> {
  const res = await fetch(`${API_BASE}/problems`);
  if (!res.ok) throw new Error(`문제 목록 조회 실패: ${res.status}`);
  const data = await res.json();
  return data.problems;
}

export async function getProblem(id: number): Promise<TeacherProblemItem> {
  const res = await fetch(`${API_BASE}/problems/${id}`);
  if (!res.ok) throw new Error(`문제 조회 실패: ${res.status}`);
  return res.json();
}

function teacherHeaders(): HeadersInit {
  const pw = localStorage.getItem("argus_teacher_pw") ?? "";
  return { "X-Teacher-Password": pw, "Content-Type": "application/json" };
}

export interface TeacherProblemListResponse {
  problems: TeacherProblemItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function getTeacherProblems(params?: {
  page?: number;
  page_size?: number;
  has_submissions?: boolean;
}): Promise<TeacherProblemListResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  if (params?.has_submissions) query.set("has_submissions", "true");
  const url = `${API_BASE}/teacher/problems${query.toString() ? `?${query.toString()}` : ""}`;
  const res = await fetch(url, { headers: teacherHeaders() });
  if (res.status === 401) throw new Error("교사 인증 실패");
  if (!res.ok) throw new Error(`문제 목록 조회 실패: ${res.status}`);
  return res.json();
}

export async function createProblem(data: ProblemCreate): Promise<TeacherProblemItem> {
  const res = await fetch(`${API_BASE}/teacher/problems`, {
    method: "POST",
    headers: teacherHeaders(),
    body: JSON.stringify(data),
  });
  if (res.status === 401) throw new Error("교사 인증 실패");
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `문제 생성 실패: ${res.status}`);
  }
  return res.json();
}

export async function updateProblem(id: number, data: Partial<ProblemCreate>): Promise<TeacherProblemItem> {
  const res = await fetch(`${API_BASE}/teacher/problems/${id}`, {
    method: "PUT",
    headers: teacherHeaders(),
    body: JSON.stringify(data),
  });
  if (res.status === 401) throw new Error("교사 인증 실패");
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `문제 수정 실패: ${res.status}`);
  }
  return res.json();
}

export async function deleteProblem(id: number): Promise<{ id: number; deleted: boolean; soft_delete: boolean }> {
  const res = await fetch(`${API_BASE}/teacher/problems/${id}`, {
    method: "DELETE",
    headers: teacherHeaders(),
  });
  if (res.status === 401) throw new Error("교사 인증 실패");
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `문제 삭제 실패: ${res.status}`);
  }
  return res.json();
}
