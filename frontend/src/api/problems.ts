import { apiFetch, teacherHeaders } from "@/api/client";

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
  const data = await apiFetch<{ problems: TeacherProblemItem[] }>("/problems", undefined, "문제 목록 조회 실패");
  return data.problems;
}

export async function getProblem(id: number): Promise<TeacherProblemItem> {
  return apiFetch(`/problems/${id}`, undefined, "문제 조회 실패");
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
  const url = `/teacher/problems${query.toString() ? `?${query.toString()}` : ""}`;
  return apiFetch(url, { headers: teacherHeaders() }, "문제 목록 조회 실패");
}

export async function createProblem(data: ProblemCreate): Promise<TeacherProblemItem> {
  return apiFetch("/teacher/problems", {
    method: "POST",
    headers: teacherHeaders(),
    body: JSON.stringify(data),
  }, "문제 생성 실패");
}

export async function updateProblem(id: number, data: Partial<ProblemCreate>): Promise<TeacherProblemItem> {
  return apiFetch(`/teacher/problems/${id}`, {
    method: "PUT",
    headers: teacherHeaders(),
    body: JSON.stringify(data),
  }, "문제 수정 실패");
}

export async function deleteProblem(id: number): Promise<{ id: number; deleted: boolean; soft_delete: boolean }> {
  return apiFetch(`/teacher/problems/${id}`, {
    method: "DELETE",
    headers: teacherHeaders(),
  }, "문제 삭제 실패");
}
