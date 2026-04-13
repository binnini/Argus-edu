import { apiFetch, apiFetchVoid, teacherHeaders } from "@/api/client";

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
  hallucination_status?: string;
  hallucination_score?: number | null;
  hallucination_issues?: string | null;
  feedback_status?: string;
  solution_status?: string | null;
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
  feedback_status: string | null;
  solution_status: string | null;
  submitted_at: string;
  reviewed_at: string | null;
}

export interface SubmissionOverviewResponse {
  submissions: SubmissionOverviewItem[];
  total: number;
  page: number;
  page_size: number;
}

function authHeaders(password: string): HeadersInit {
  return teacherHeaders(true, password);
}

export async function getTeacherQueue(
  password: string,
  trustLevel?: string,
): Promise<TeacherQueueResponse> {
  const params = new URLSearchParams();
  if (trustLevel) params.set("trust_level", trustLevel);
  const url = `/teacher/queue${params.toString() ? `?${params.toString()}` : ""}`;
  return apiFetch(url, {
    headers: authHeaders(password),
  }, "큐 조회 실패");
}

export async function getQueue(trustLevel?: string): Promise<TeacherQueueResponse> {
  const params = new URLSearchParams();
  if (trustLevel) params.set("trust_level", trustLevel);
  const url = `/teacher/queue${params.toString() ? `?${params.toString()}` : ""}`;
  return apiFetch(url, { headers: teacherHeaders() }, "큐 조회 실패");
}

export async function submitTeacherAction(
  queueId: number,
  payload: TeacherActionRequest,
  password: string
): Promise<TeacherActionResponse> {
  return apiFetch(`/teacher/queue/${queueId}/action`, {
    method: "POST",
    headers: authHeaders(password),
    body: JSON.stringify(payload),
  }, "액션 제출 실패");
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
  return apiFetch("/teacher/feedback/summary", {
    headers: authHeaders(password),
  }, "피드백 현황 조회 실패");
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
  const url = `/teacher/submissions?${query.toString()}`;
  return apiFetch(url, { headers: teacherHeaders() }, "제출 현황 조회 실패");
}

export async function getProblemSubmissions(
  problemId: number,
  params?: { page?: number; page_size?: number },
): Promise<SubmissionOverviewResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  const url = `/teacher/problems/${problemId}/submissions?${query.toString()}`;
  return apiFetch(url, { headers: teacherHeaders() }, "제출 목록 조회 실패");
}

// ===== 그룹 관리 =====

export interface GroupMemberItem { student_id: string; student_name: string }
export interface GroupResponse { id: number; name: string; created_at: string; members: GroupMemberItem[] }
export interface GroupListResponse { groups: GroupResponse[] }

export async function getGroups(): Promise<GroupListResponse> {
  return apiFetch("/teacher/groups", { headers: teacherHeaders(false) }, "그룹 목록 조회 실패");
}

export async function createGroup(name: string): Promise<GroupResponse> {
  return apiFetch("/teacher/groups", {
    method: "POST",
    headers: teacherHeaders(),
    body: JSON.stringify({ name }),
  }, "그룹 생성 실패");
}

export async function deleteGroup(groupId: number): Promise<void> {
  return apiFetchVoid(`/teacher/groups/${groupId}`, {
    method: "DELETE",
    headers: teacherHeaders(false),
  }, "그룹 삭제 실패");
}

export async function addGroupMembers(groupId: number, members: GroupMemberItem[]): Promise<void> {
  return apiFetchVoid(`/teacher/groups/${groupId}/members`, {
    method: "POST",
    headers: teacherHeaders(),
    body: JSON.stringify({ members }),
  }, "멤버 추가 실패");
}

export async function removeGroupMember(groupId: number, studentId: string): Promise<void> {
  return apiFetchVoid(`/teacher/groups/${groupId}/members/${encodeURIComponent(studentId)}`, {
    method: "DELETE",
    headers: teacherHeaders(false),
  }, "멤버 제거 실패");
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
  return apiFetch("/teacher/homeworks", { headers: teacherHeaders(false) }, "숙제 목록 조회 실패");
}

export async function createHomework(payload: {
  title: string;
  group_id?: number | null;
  due_date?: string | null;
  problem_ids: number[];
}): Promise<HomeworkResponse> {
  return apiFetch("/teacher/homeworks", {
    method: "POST",
    headers: teacherHeaders(),
    body: JSON.stringify(payload),
  }, "숙제 생성 실패");
}

export async function deleteHomework(homeworkId: number): Promise<void> {
  return apiFetchVoid(`/teacher/homeworks/${homeworkId}`, {
    method: "DELETE",
    headers: teacherHeaders(false),
  }, "숙제 삭제 실패");
}
