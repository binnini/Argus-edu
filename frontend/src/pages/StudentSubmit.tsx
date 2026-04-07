import { useState, useEffect } from "react";
import {
  getProblems,
  submitAnswerText,
  submitAnswerImage,
  getSubmissionStatus,
  Problem,
  SubmissionStatusResponse,
} from "../api/submissions";
import AnswerInput from "../components/AnswerInput";
import FeedbackPanel from "../components/FeedbackPanel";

type AppState =
  | { phase: "loading" }
  | { phase: "select"; problems: Problem[] }
  | { phase: "form"; problems: Problem[]; selectedId: number }
  | { phase: "polling"; submissionId: number; result: SubmissionStatusResponse | null }
  | { phase: "error"; message: string };

export default function StudentSubmit() {
  const [state, setState] = useState<AppState>({ phase: "loading" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getProblems()
      .then((problems) => setState({ phase: "select", problems }))
      .catch((e) => setState({ phase: "error", message: e.message }));
  }, []);

  // 폴링: 2초 간격, teacher_approved 또는 rejected될 때까지 지속
  useEffect(() => {
    if (state.phase !== "polling") return;
    const { submissionId, result } = state;

    if (result?.teacher_approved || result?.status === "rejected") return;

    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      if (attempts > 300) {
        // 10분 폴링 상한
        clearInterval(interval);
        return;
      }
      try {
        const updated = await getSubmissionStatus(submissionId);
        setState((prev) =>
          prev.phase === "polling" ? { ...prev, result: updated } : prev
        );
        if (updated.teacher_approved || updated.status === "rejected") {
          clearInterval(interval);
        }
      } catch {
        // 폴링 중 네트워크 오류 무시
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [state.phase === "polling" ? state.submissionId : null]);

  async function handleSubmitText(answer: string) {
    if (state.phase !== "form") return;
    setSubmitting(true);
    try {
      const resp = await submitAnswerText(state.selectedId, answer);
      setState({ phase: "polling", submissionId: resp.submission_id, result: null });
    } catch (e) {
      setState({ phase: "error", message: e instanceof Error ? e.message : "제출 실패" });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmitImage(file: File) {
    if (state.phase !== "form") return;
    setSubmitting(true);
    try {
      const resp = await submitAnswerImage(state.selectedId, file);
      setState({ phase: "polling", submissionId: resp.submission_id, result: null });
    } catch (e) {
      setState({ phase: "error", message: e instanceof Error ? e.message : "이미지 제출 실패" });
    } finally {
      setSubmitting(false);
    }
  }

  if (state.phase === "loading") {
    return <div style={styles.center}>문제 목록 불러오는 중...</div>;
  }

  if (state.phase === "error") {
    return (
      <div style={styles.center}>
        <p style={{ color: "red" }}>오류: {state.message}</p>
        <button onClick={() => window.location.reload()}>새로고침</button>
      </div>
    );
  }

  if (state.phase === "select") {
    return (
      <div style={styles.container}>
        <h1>수학 서답형 채점 시스템</h1>
        <h2>문제를 선택하세요</h2>
        <ul style={styles.problemList}>
          {state.problems.map((p) => (
            <li
              key={p.id}
              style={styles.problemItem}
              onClick={() =>
                setState({ phase: "form", problems: state.problems, selectedId: p.id })
              }
            >
              <strong>{p.title}</strong>
              <span style={styles.badge}>{p.domain}</span>
              <span style={styles.badge}>난이도 {p.difficulty}</span>
              <span style={styles.badge}>{p.total_score}점</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (state.phase === "form") {
    const problem = state.problems.find((p) => p.id === state.selectedId)!;
    return (
      <div style={styles.container}>
        <button onClick={() => setState({ phase: "select", problems: state.problems })}>
          ← 문제 목록
        </button>
        <h2>{problem.title}</h2>
        <div style={styles.problemBox}>{problem.content}</div>
        <p style={{ color: "#666", fontSize: "0.9rem" }}>배점: {problem.total_score}점</p>

        <AnswerInput
          onSubmitText={handleSubmitText}
          onSubmitImage={handleSubmitImage}
          disabled={submitting}
        />
      </div>
    );
  }

  if (state.phase === "polling") {
    const { result } = state;
    return (
      <div style={styles.container}>
        <h2>채점 결과</h2>

        {!result && (
          <div style={styles.waitingBox}>
            <p>채점 중입니다. 잠시 기다려 주세요...</p>
            <div style={styles.spinner} />
          </div>
        )}

        {result && (
          <div style={styles.resultBox}>
            {result.score_visible && result.score !== null && (
              <p style={styles.scoreText}>
                점수: <strong>{result.score}점</strong>
              </p>
            )}

            <p>
              <strong>상태:</strong> {statusLabel(result.status)}
            </p>

            {/* 개인화 피드백 — teacher_approved === true일 때만 */}
            {result.teacher_approved && result.feedback ? (
              <FeedbackPanel feedback={result.feedback} />
            ) : (
              <p style={styles.waitingMsg}>
                {result.message ?? "교사 검토 중입니다. 피드백은 검토 완료 후 확인할 수 있습니다."}
              </p>
            )}
          </div>
        )}

        <button
          style={{ marginTop: "1.5rem" }}
          onClick={() => setState({ phase: "loading" })}
        >
          새 문제 풀기
        </button>
      </div>
    );
  }

  return null;
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "채점 대기 중",
    graded: "채점 완료 (교사 검토 중)",
    approved: "교사 승인 완료",
    rejected: "교사 거부",
    error: "오류 발생",
  };
  return map[status] ?? status;
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 720, margin: "2rem auto", padding: "0 1rem", fontFamily: "sans-serif" },
  center: { textAlign: "center", marginTop: "4rem" },
  problemList: { listStyle: "none", padding: 0 },
  problemItem: {
    padding: "1rem",
    border: "1px solid #ddd",
    borderRadius: 8,
    marginBottom: "0.75rem",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
  },
  badge: {
    background: "#eef",
    borderRadius: 4,
    padding: "2px 8px",
    fontSize: "0.8rem",
  },
  problemBox: {
    background: "#f9f9f9",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    padding: "1rem",
    margin: "1rem 0",
    whiteSpace: "pre-wrap",
  },
  resultBox: {
    background: "#f0f7ff",
    border: "1px solid #bdd7ff",
    borderRadius: 8,
    padding: "1.5rem",
  },
  scoreText: {
    fontSize: "1.2rem",
    margin: "0 0 0.75rem",
  },
  waitingBox: {
    textAlign: "center",
    padding: "2rem",
    color: "#666",
  },
  spinner: {
    margin: "1rem auto",
    width: 32,
    height: 32,
    border: "3px solid #e0e0e0",
    borderTop: "3px solid #2563eb",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
  },
  waitingMsg: {
    color: "#555",
    marginTop: "1rem",
    fontSize: "0.9rem",
  },
};
