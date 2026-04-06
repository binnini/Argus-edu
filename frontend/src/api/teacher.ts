const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export interface QueueItem {
  queue_id: number;
  submission_id: number;
  problem_title: string;
  student_answer: string;
  ai_score: number;
  ai_explanation: string;
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
  teacher_explanation?: string;
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

function authHeaders(password: string): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Teacher-Password": password,
  };
}

export async function getTeacherQueue(
  password: string
): Promise<TeacherQueueResponse> {
  const res = await fetch(`${API_BASE}/teacher/queue`, {
    headers: authHeaders(password),
  });
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
    throw new Error(err.detail ?? `액션 제출 실패: ${res.status}`);
  }
  return res.json();
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
