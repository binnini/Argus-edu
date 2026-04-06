import { useState, useEffect } from "react";
import {
  getTeacherQueue,
  submitTeacherAction,
  QueueItem,
  TeacherAction,
} from "../api/teacher";

type DashboardState =
  | { phase: "login" }
  | { phase: "loading"; password: string }
  | { phase: "queue"; password: string; items: QueueItem[]; total: number }
  | { phase: "review"; password: string; items: QueueItem[]; total: number; selected: QueueItem }
  | { phase: "error"; message: string; password: string };

export default function TeacherDashboard() {
  const [state, setState] = useState<DashboardState>({ phase: "login" });
  const [password, setPassword] = useState("");
  const [action, setAction] = useState<TeacherAction>("approve");
  const [teacherScore, setTeacherScore] = useState("");
  const [teacherExplanation, setTeacherExplanation] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleLogin() {
    if (!password.trim()) return;
    setState({ phase: "loading", password });
    try {
      const resp = await getTeacherQueue(password);
      setState({ phase: "queue", password, items: resp.queue, total: resp.total });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "오류";
      setState({ phase: "error", message: msg, password });
    }
  }

  async function handleAction(queueId: number) {
    if (state.phase !== "review") return;
    setSubmitting(true);
    try {
      const payload =
        action === "modify"
          ? {
              action,
              teacher_score: Number(teacherScore),
              teacher_explanation: teacherExplanation,
            }
          : { action };

      await submitTeacherAction(queueId, payload, state.password);

      // 큐 새로고침
      const resp = await getTeacherQueue(state.password);
      setState({ phase: "queue", password: state.password, items: resp.queue, total: resp.total });
      setAction("approve");
      setTeacherScore("");
      setTeacherExplanation("");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "오류";
      alert(`액션 제출 실패: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }

  if (state.phase === "login") {
    return (
      <div style={styles.center}>
        <h1>교사 대시보드</h1>
        <div style={styles.loginBox}>
          <input
            type="password"
            placeholder="교사 비밀번호"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            style={styles.input}
          />
          <button style={styles.primaryBtn} onClick={handleLogin}>
            입장
          </button>
        </div>
      </div>
    );
  }

  if (state.phase === "loading") {
    return <div style={styles.center}>큐 불러오는 중...</div>;
  }

  if (state.phase === "error") {
    return (
      <div style={styles.center}>
        <p style={{ color: "red" }}>{state.message}</p>
        <button onClick={() => setState({ phase: "login" })}>다시 로그인</button>
      </div>
    );
  }

  if (state.phase === "queue") {
    const { items, total, password: pw } = state;
    return (
      <div style={styles.container}>
        <h1>교사 검토 큐 ({total}건)</h1>
        {items.length === 0 ? (
          <p>검토 대기 항목이 없습니다.</p>
        ) : (
          <ul style={styles.queueList}>
            {items.map((item) => (
              <li key={item.queue_id} style={styles.queueItem}>
                <div style={styles.queueHeader}>
                  <strong>{item.problem_title}</strong>
                  <TrustBadge level={item.trust_level} score={item.trust_score} />
                  <span style={styles.typeBadge}>{item.queue_type === "full_review" ? "전체 검토" : "풀이 검토"}</span>
                </div>
                <p style={styles.queueMeta}>
                  SLA: {formatDeadline(item.sla_deadline)} 남음 | AI 점수: {item.ai_score}점
                </p>
                <p style={styles.studentAnswer}>학생 답변: {item.student_answer}</p>
                <button
                  style={styles.primaryBtn}
                  onClick={() =>
                    setState({ phase: "review", password: pw, items, total, selected: item })
                  }
                >
                  검토하기
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  if (state.phase === "review") {
    const { selected, password: pw, items, total } = state;
    return (
      <div style={styles.container}>
        <button onClick={() => setState({ phase: "queue", password: pw, items, total })}>
          ← 목록으로
        </button>
        <h2>{selected.problem_title}</h2>

        <div style={styles.infoBox}>
          <TrustBadge level={selected.trust_level} score={selected.trust_score} />
          <p>AI 점수: {selected.ai_score}점</p>
          <p>SLA 마감: {new Date(selected.sla_deadline).toLocaleString("ko-KR")}</p>
        </div>

        <h3>학생 답변</h3>
        <div style={styles.contentBox}>{selected.student_answer}</div>

        <h3>AI 풀이 설명</h3>
        <div style={styles.contentBox}>{selected.ai_explanation}</div>

        <h3>액션 선택 (3가지 중 하나)</h3>
        <div style={styles.actionGroup}>
          {(["approve", "modify", "reject"] as TeacherAction[]).map((a) => (
            <label key={a} style={styles.actionLabel}>
              <input
                type="radio"
                name="action"
                value={a}
                checked={action === a}
                onChange={() => setAction(a)}
              />
              {a === "approve" ? "승인" : a === "modify" ? "수정" : "거부"}
            </label>
          ))}
        </div>

        {action === "modify" && (
          <div style={styles.modifyForm}>
            <label>
              교사 확정 점수
              <input
                type="number"
                value={teacherScore}
                onChange={(e) => setTeacherScore(e.target.value)}
                style={{ ...styles.input, width: 80 }}
                min={0}
              />
            </label>
            <label>
              수정 풀이 설명
              <textarea
                value={teacherExplanation}
                onChange={(e) => setTeacherExplanation(e.target.value)}
                style={{ ...styles.textarea, marginTop: "0.5rem" }}
                rows={4}
                placeholder="수정된 풀이 설명을 입력하세요..."
              />
            </label>
          </div>
        )}

        <button
          style={{ ...styles.primaryBtn, marginTop: "1rem" }}
          onClick={() => handleAction(selected.queue_id)}
          disabled={submitting || (action === "modify" && (!teacherScore || !teacherExplanation))}
        >
          {submitting ? "제출 중..." : "제출"}
        </button>
      </div>
    );
  }

  return null;
}

function TrustBadge({ level, score }: { level: "high" | "low"; score: number }) {
  return (
    <span
      style={{
        background: level === "high" ? "#d1fae5" : "#fee2e2",
        color: level === "high" ? "#065f46" : "#991b1b",
        borderRadius: 4,
        padding: "2px 8px",
        fontSize: "0.85rem",
        fontWeight: "bold",
      }}
    >
      {level === "high" ? "신뢰도 High" : "신뢰도 Low"} ({score.toFixed(2)})
    </span>
  );
}

function formatDeadline(deadline: string): string {
  const diff = new Date(deadline).getTime() - Date.now();
  if (diff <= 0) return "마감";
  const hours = Math.floor(diff / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  return `${hours}시간 ${minutes}분`;
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 800, margin: "2rem auto", padding: "0 1rem", fontFamily: "sans-serif" },
  center: { textAlign: "center", marginTop: "4rem", fontFamily: "sans-serif" },
  loginBox: { display: "flex", gap: "0.5rem", justifyContent: "center", marginTop: "1rem" },
  input: { padding: "0.5rem 0.75rem", fontSize: "1rem", border: "1px solid #ccc", borderRadius: 6 },
  textarea: { width: "100%", padding: "0.5rem", fontSize: "0.95rem", border: "1px solid #ccc", borderRadius: 6, boxSizing: "border-box" },
  primaryBtn: {
    padding: "0.6rem 1.5rem",
    background: "#2563eb",
    color: "white",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: "0.95rem",
  },
  queueList: { listStyle: "none", padding: 0 },
  queueItem: {
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    padding: "1rem",
    marginBottom: "0.75rem",
  },
  queueHeader: { display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" },
  typeBadge: { background: "#ede9fe", borderRadius: 4, padding: "2px 8px", fontSize: "0.8rem" },
  queueMeta: { fontSize: "0.85rem", color: "#555", margin: "0.25rem 0" },
  studentAnswer: { fontSize: "0.9rem", color: "#333", marginBottom: "0.75rem", fontStyle: "italic" },
  infoBox: { display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" },
  contentBox: {
    background: "#f9f9f9",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    padding: "1rem",
    marginBottom: "1rem",
    whiteSpace: "pre-wrap",
    fontSize: "0.95rem",
  },
  actionGroup: { display: "flex", gap: "1.5rem", marginBottom: "1rem" },
  actionLabel: { display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer" },
  modifyForm: { display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" },
};
