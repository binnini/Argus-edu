const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface QueueItem {
  queue_id: number;
  submission_id: number;
  problem_title: string;
  problem_content: string;
  problem_answer: string;
  ocr_raw_text: string | null;
  student_answer: string;
  student_name: string;
  student_id: string | null;
  input_type: string;
  image_path: string | null;
  ai_score: number;
  ai_feedback: string;
  trust_score: number;
  trust_level: "high" | "low";
  queue_type: "score_only" | "full_review";
  sla_deadline: string;
  queued_at: string;
}

export interface TeacherQueueResponse {
  queue: QueueItem[];
  total: number;
}

export type TeacherAction = "approve" | "modify" | "reject";

export interface TeacherActionRequest {
  action: TeacherAction;
  teacher_score?: number;
  teacher_feedback?: string;
}

export interface TeacherActionResponse {
  queue_id: number;
  action: string;
  reviewed_at: string;
}

export interface FeedbackSummary {
  total_reviewed: number;
  approved: number;
  modified: number;
  rejected: number;
  approval_rate: number;
  avg_score_delta: number;
  low_trust_detection_precision: number;
}

export interface SubmissionOverviewItem {
  submission_id: number;
  problem_id: number;
  problem_title: string;
  student_name: string;
  student_id: string | null;
  input_type: string;
  image_path: string | null;
  status: string;
  ai_score: number | null;
  final_score: number | null;
  trust_level: string | null;
  submitted_at: string;
  reviewed_at: string | null;
}

export interface SubmissionOverviewResponse {
  submissions: SubmissionOverviewItem[];
  total: number;
  page: number;
  page_size: number;
}

function teacherHeaders(extraContentType = true): HeadersInit {
  const pw = localStorage.getItem("argus_teacher_pw") ?? "";
  const headers: Record<string, string> = {
    "X-Teacher-Password": pw,
  };
  if (extraContentType) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function authHeaders(password: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Teacher-Password": password,
  };
}

export async function getTeacherQueue(
  password: string,
  trustLevel?: string,
): Promise<TeacherQueueResponse> {
  const params = new URLSearchParams();
  if (trustLevel) params.set("trust_level", trustLevel);
  const url = `${API_BASE}/teacher/queue${params.toString() ? `?${params.toString()}` : ""}`;
  const res = await fetch(url, {
    headers: authHeaders(password),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`큐 조회 실패: ${res.status}`);
  return res.json();
}

export async function getQueue(trustLevel?: string): Promise<TeacherQueueResponse> {
  const params = new URLSearchParams();
  if (trustLevel) params.set("trust_level", trustLevel);
  const url = `${API_BASE}/teacher/queue${params.toString() ? `?${params.toString()}` : ""}`;
  const res = await fetch(url, { headers: teacherHeaders() });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`큐 조회 실패: ${res.status}`);
  return res.json();
}

export async function submitTeacherAction(
  queueId: number,
  payload: TeacherActionRequest,
  password: string
): Promise<TeacherActionResponse> {
  const res = await fetch(`${API_BASE}/teacher/queue/${queueId}/action`, {
    method: "POST",
    headers: authHeaders(password),
    body: JSON.stringify(payload),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `액션 제출 실패: ${res.status}`);
  }
  return res.json();
}

export async function postTeacherAction(
  queueId: number,
  payload: TeacherActionRequest,
): Promise<TeacherActionResponse> {
  const pw = localStorage.getItem("argus_teacher_pw") ?? "";
  return submitTeacherAction(queueId, payload, pw);
}

export async function getFeedbackSummary(
  password: string
): Promise<FeedbackSummary> {
  const res = await fetch(`${API_BASE}/teacher/feedback/summary`, {
    headers: authHeaders(password),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`피드백 현황 조회 실패: ${res.status}`);
  return res.json();
}

export async function getSubmissions(params: {
  problem_id?: number;
  status?: string;
  student_name?: string;
  page?: number;
  page_size?: number;
}): Promise<SubmissionOverviewResponse> {
  const query = new URLSearchParams();
  if (params.problem_id) query.set("problem_id", String(params.problem_id));
  if (params.status) query.set("status", params.status);
  if (params.student_name) query.set("student_name", params.student_name);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const url = `${API_BASE}/teacher/submissions?${query.toString()}`;
  const res = await fetch(url, { headers: teacherHeaders() });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`제출 현황 조회 실패: ${res.status}`);
  return res.json();
}

export async function getProblemSubmissions(
  problemId: number,
  params?: { page?: number; page_size?: number },
): Promise<SubmissionOverviewResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  const url = `${API_BASE}/teacher/problems/${problemId}/submissions?${query.toString()}`;
  const res = await fetch(url, { headers: teacherHeaders() });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`제출 목록 조회 실패: ${res.status}`);
  return res.json();
}
