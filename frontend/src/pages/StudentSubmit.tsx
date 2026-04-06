import { useState, useEffect } from "react";
import {
  getProblems,
  submitAnswer,
  getSubmissionStatus,
  Problem,
  SubmissionStatusResponse,
} from "../api/submissions";

type AppState =
  | { phase: "loading" }
  | { phase: "select"; problems: Problem[] }
  | { phase: "form"; problems: Problem[]; selectedId: number }
  | { phase: "polling"; submissionId: number; result: SubmissionStatusResponse | null }
  | { phase: "error"; message: string };

export default function StudentSubmit() {
  const [state, setState] = useState<AppState>({ phase: "loading" });
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getProblems()
      .then((problems) => setState({ phase: "select", problems }))
      .catch((e) => setState({ phase: "error", message: e.message }));
  }, []);

  // 폴링: 2초 간격, 최대 60초 (30회)
  useEffect(() => {
    if (state.phase !== "polling") return;
    const { submissionId, result } = state;

    if (result?.teacher_approved || result?.status === "rejected") return;

    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      if (attempts > 30) {
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
        // 폴링 중 네트워크 오류는 무시하고 계속
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [state.phase === "polling" ? state.submissionId : null]);

  async function handleSubmit() {
    if (state.phase !== "form") return;
    if (!answer.trim()) return;
    setSubmitting(true);
    try {
      const resp = await submitAnswer({
        problem_id: state.selectedId,
        student_answer: answer,
      });
      setState({ phase: "polling", submissionId: resp.submission_id, result: null });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "제출 실패";
      setState({ phase: "error", message: msg });
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
        <p>배점: {problem.total_score}점</p>
        <textarea
          style={styles.textarea}
          placeholder="풀이와 답을 입력하세요..."
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={6}
        />
        <button
          style={styles.submitBtn}
          onClick={handleSubmit}
          disabled={submitting || !answer.trim()}
        >
          {submitting ? "제출 중..." : "답변 제출"}
        </button>
      </div>
    );
  }

  if (state.phase === "polling") {
    const { result } = state;
    return (
      <div style={styles.container}>
        <h2>채점 결과</h2>

        {!result && <p>채점 중입니다. 잠시 기다려 주세요...</p>}

        {result && (
          <div style={styles.resultBox}>
            {result.score_visible && result.score !== null && (
              <p>
                <strong>점수:</strong> {result.score}점
              </p>
            )}

            {/* 풀이 설명은 teacher_approved === true일 때만 표시 */}
            {result.teacher_approved && result.explanation ? (
              <div>
                <strong>풀이 설명:</strong>
                <div style={styles.explanationBox}>{result.explanation}</div>
              </div>
            ) : (
              <p style={{ color: "#666" }}>
                {result.message ?? "교사 검토 중입니다. 풀이 설명은 검토 완료 후 확인할 수 있습니다."}
              </p>
            )}

            <p>
              <strong>상태:</strong> {statusLabel(result.status)}
            </p>
          </div>
        )}

        <button
          style={{ marginTop: "1rem" }}
          onClick={() =>
            setState({ phase: "loading" })
          }
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
  },
  textarea: { width: "100%", padding: "0.75rem", fontSize: "1rem", borderRadius: 8, border: "1px solid #ccc", boxSizing: "border-box" },
  submitBtn: {
    marginTop: "1rem",
    padding: "0.75rem 2rem",
    background: "#2563eb",
    color: "white",
    border: "none",
    borderRadius: 8,
    fontSize: "1rem",
    cursor: "pointer",
  },
  resultBox: {
    background: "#f0f7ff",
    border: "1px solid #bdd7ff",
    borderRadius: 8,
    padding: "1.5rem",
  },
  explanationBox: {
    background: "white",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    padding: "1rem",
    marginTop: "0.5rem",
    whiteSpace: "pre-wrap",
  },
};
