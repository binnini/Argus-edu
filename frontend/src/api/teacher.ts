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
  student_answer: string | null;
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

// ===== 그룹 관리 =====

export interface GroupMemberItem { student_id: string; student_name: string }
export interface GroupResponse { id: number; name: string; created_at: string; members: GroupMemberItem[] }
export interface GroupListResponse { groups: GroupResponse[] }

export async function getGroups(): Promise<GroupListResponse> {
  const res = await fetch(`${API_BASE}/teacher/groups`, { headers: teacherHeaders(false) });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`그룹 목록 조회 실패: ${res.status}`);
  return res.json();
}

export async function createGroup(name: string): Promise<GroupResponse> {
  const res = await fetch(`${API_BASE}/teacher/groups`, {
    method: "POST",
    headers: teacherHeaders(),
    body: JSON.stringify({ name }),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`그룹 생성 실패: ${res.status}`);
  return res.json();
}

export async function deleteGroup(groupId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/teacher/groups/${groupId}`, {
    method: "DELETE",
    headers: teacherHeaders(false),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`그룹 삭제 실패: ${res.status}`);
}

export async function addGroupMembers(groupId: number, members: GroupMemberItem[]): Promise<void> {
  const res = await fetch(`${API_BASE}/teacher/groups/${groupId}/members`, {
    method: "POST",
    headers: teacherHeaders(),
    body: JSON.stringify({ members }),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`멤버 추가 실패: ${res.status}`);
}

export async function removeGroupMember(groupId: number, studentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/teacher/groups/${groupId}/members/${encodeURIComponent(studentId)}`, {
    method: "DELETE",
    headers: teacherHeaders(false),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`멤버 제거 실패: ${res.status}`);
}

// ===== 숙제 관리 =====

export interface HomeworkProblemItem { problem_id: number; problem_title: string }
export interface HomeworkResponse {
  id: number;
  title: string;
  group_id: number | null;
  group_name: string | null;
  due_date: string | null;
  created_at: string;
  problems: HomeworkProblemItem[];
}
export interface HomeworkListResponse { homeworks: HomeworkResponse[] }

export async function getHomeworks(): Promise<HomeworkListResponse> {
  const res = await fetch(`${API_BASE}/teacher/homeworks`, { headers: teacherHeaders(false) });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`숙제 목록 조회 실패: ${res.status}`);
  return res.json();
}

export async function createHomework(payload: {
  title: string;
  group_id?: number | null;
  due_date?: string | null;
  problem_ids: number[];
}): Promise<HomeworkResponse> {
  const res = await fetch(`${API_BASE}/teacher/homeworks`, {
    method: "POST",
    headers: teacherHeaders(),
    body: JSON.stringify(payload),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`숙제 생성 실패: ${res.status}`);
  return res.json();
}

export async function deleteHomework(homeworkId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/teacher/homeworks/${homeworkId}`, {
    method: "DELETE",
    headers: teacherHeaders(false),
  });
  if (res.status === 401) throw new Error("비밀번호가 올바르지 않습니다");
  if (!res.ok) throw new Error(`숙제 삭제 실패: ${res.status}`);
}
