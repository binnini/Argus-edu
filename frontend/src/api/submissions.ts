import { apiFetch } from "@/api/client";

export interface Problem {
  id: number;
  title: string;
  content: string;
  domain: string;
  school_level?: string | null;
  difficulty: number;
  total_score: number;
}

export interface FeedbackMistake {
  step: number | null;
  description: string;
}

export interface FeedbackStep {
  step: number;
  title: string;
  content: string;
}

export interface Feedback {
  solution_status?: string | null;
  has_mistakes?: boolean;
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
  submitted_at: string | null;
  status: string;
  score: number | null;
  max_score: number | null;     // 문제 만점 (부분 정답 판별용)
  score_visible: boolean;
  feedback: Feedback | null;    // 교사 승인 또는 feedback_visible 시 노출
  feedback_visible: boolean;    // 정답+고신뢰도면 교사 승인 전에도 노출
  feedback_status: string | null;
  graded_at: string | null;
  feedback_completed_at: string | null;
  solution_status: string | null;
  hallucination_status: string | null;
  hallucination_completed_at: string | null;
  teacher_approved: boolean;
  message: string | null;
  problem_title: string | null;
  problem_content: string | null;
}

export interface ProblemListPagedResponse {
  problems: Problem[];
  total: number;
  page: number;
  page_size: number;
}

export interface StudentHistoryItem {
  submission_id: number;
  problem_title: string;
  problem_domain: string;
  status: string;
  ai_score: number | null;
  final_score: number | null;
  input_type: string;
  submitted_at: string;
  image_path: string | null;
  student_answer: string | null;
}

export interface StudentHistoryResponse {
  submissions: StudentHistoryItem[];
}

export async function getProblems(
  page = 1,
  pageSize = 10,
  options?: { q?: string; domain?: string; school_level?: string; difficulty?: number },
): Promise<ProblemListPagedResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (options?.q) params.set("q", options.q);
  if (options?.domain) params.set("domain", options.domain);
  if (options?.school_level) params.set("school_level", options.school_level);
  if (options?.difficulty != null) params.set("difficulty", String(options.difficulty));
  return apiFetch(`/problems?${params.toString()}`, undefined, "문제 목록 조회 실패");
}

export async function getStudentHistory(studentId: string): Promise<StudentHistoryResponse> {
  return apiFetch(`/submissions?student_id=${encodeURIComponent(studentId)}`, undefined, "이력 조회 실패");
}

export async function getProblem(problemId: number): Promise<Problem> {
  return apiFetch(`/problems/${problemId}`, undefined, "문제 조회 실패");
}

export async function verifyStudent(
  studentId: string,
  studentName: string,
): Promise<{ valid: boolean; message: string }> {
  const params = new URLSearchParams({ student_id: studentId, student_name: studentName });
  return apiFetch(`/students/verify?${params.toString()}`, undefined, "인증 확인 실패");
}

export async function submitAnswerText(
  problemId: number,
  studentAnswer: string,
  studentName: string,
  studentId?: string,
  finalAnswer?: string,
): Promise<SubmissionCreateResponse> {
  return apiFetch("/submissions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      problem_id: problemId,
      student_answer: studentAnswer,
      student_name: studentName,
      student_id: studentId ?? null,
      final_answer: finalAnswer ?? null,
    }),
  }, "제출 실패");
}

export async function submitAnswerImage(
  problemId: number,
  imageFile: File,
  studentName: string,
  studentId?: string,
  finalAnswer?: string,
): Promise<SubmissionCreateResponse> {
  const formData = new FormData();
  formData.append("problem_id", String(problemId));
  formData.append("image", imageFile);
  formData.append("student_name", studentName);
  if (studentId) {
    formData.append("student_id", studentId);
  }
  if (finalAnswer && finalAnswer.trim()) {
    formData.append("student_final_answer", finalAnswer.trim());
  }

  return apiFetch("/submissions/image", {
    method: "POST",
    body: formData,
  }, "이미지 제출 실패");
}

export async function getSubmissionStatus(
  submissionId: number
): Promise<SubmissionStatusResponse> {
  return apiFetch(`/submissions/${submissionId}`, undefined, "채점 결과 조회 실패");
}

export interface HomeworkProblemStatus {
  problem_id: number;
  problem_title: string;
  submitted: boolean;
  status: string | null;
}

export interface StudentHomeworkItem {
  homework_id: number;
  title: string;
  group_name: string | null;
  due_date: string | null;
  total_problems: number;
  completed_problems: number;
  problems: HomeworkProblemStatus[];
}

export interface StudentHomeworkResponse {
  homeworks: StudentHomeworkItem[];
}

export async function getStudentHomework(studentId: string): Promise<StudentHomeworkResponse> {
  return apiFetch(`/submissions/homework?student_id=${encodeURIComponent(studentId)}`, undefined, "숙제 조회 실패");
}
