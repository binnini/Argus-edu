import { useState } from "react";
import {
  getTeacherQueue,
  QueueItem,
} from "../api/teacher";
import ReviewCard from "../components/ReviewCard";

const PASSWORD_KEY = "argus_teacher_password";

type DashboardState =
  | { phase: "login" }
  | { phase: "loading"; password: string }
  | { phase: "queue"; password: string; items: QueueItem[]; total: number }
  | { phase: "review"; password: string; items: QueueItem[]; total: number; selected: QueueItem }
  | { phase: "error"; message: string; password: string };

export default function TeacherDashboard() {
  const [state, setState] = useState<DashboardState>(() => {
    const saved = localStorage.getItem(PASSWORD_KEY);
    return saved ? { phase: "login" } : { phase: "login" };
  });
  const [password, setPassword] = useState<string>(
    () => localStorage.getItem(PASSWORD_KEY) ?? ""
  );

  async function handleLogin() {
    if (!password.trim()) return;
    setState({ phase: "loading", password });
    try {
      const resp = await getTeacherQueue(password);
      localStorage.setItem(PASSWORD_KEY, password);
      setState({ phase: "queue", password, items: resp.queue, total: resp.total });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "오류";
      localStorage.removeItem(PASSWORD_KEY);
      setState({ phase: "error", message: msg, password });
    }
  }

  async function refreshQueue(pw: string) {
    try {
      const resp = await getTeacherQueue(pw);
      setState({ phase: "queue", password: pw, items: resp.queue, total: resp.total });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "오류";
      setState({ phase: "error", message: msg, password: pw });
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
        <button
          onClick={() => {
            localStorage.removeItem(PASSWORD_KEY);
            setState({ phase: "login" });
          }}
        >
          다시 로그인
        </button>
      </div>
    );
  }

  if (state.phase === "queue") {
    const { items, total, password: pw } = state;
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h1>교사 검토 큐 ({total}건)</h1>
          <button
            style={styles.secondaryBtn}
            onClick={() => refreshQueue(pw)}
          >
            새로고침
          </button>
          <button
            style={styles.logoutBtn}
            onClick={() => {
              localStorage.removeItem(PASSWORD_KEY);
              setState({ phase: "login" });
            }}
          >
            로그아웃
          </button>
        </div>

        {items.length === 0 ? (
          <p>검토 대기 항목이 없습니다.</p>
        ) : (
          <ul style={styles.queueList}>
            {items.map((item) => (
              <li key={item.queue_id} style={styles.queueItem}>
                <div style={styles.queueHeader}>
                  <strong>{item.problem_title}</strong>
                  <TrustBadge level={item.trust_level} score={item.trust_score} />
                  <span style={styles.typeBadge}>
                    {item.queue_type === "full_review" ? "전체 검토" : "풀이 검토"}
                  </span>
                </div>
                <p style={styles.queueMeta}>
                  SLA: {formatDeadline(item.sla_deadline)} 남음 &nbsp;|&nbsp; AI 점수:{" "}
                  {item.ai_score}점
                </p>
                <p style={styles.studentAnswer}>학생 답변: {item.student_answer}</p>
                <button
                  style={styles.primaryBtn}
                  onClick={() =>
                    setState({
                      phase: "review",
                      password: pw,
                      items,
                      total,
                      selected: item,
                    })
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
      <ReviewCard
        item={selected}
        password={pw}
        onBack={() => setState({ phase: "queue", password: pw, items, total })}
        onSuccess={() => refreshQueue(pw)}
      />
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
  const hours = Math.floor(diff / 3_600_000);
  const minutes = Math.floor((diff % 3_600_000) / 60_000);
  return `${hours}시간 ${minutes}분`;
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 800, margin: "2rem auto", padding: "0 1rem", fontFamily: "sans-serif" },
  center: { textAlign: "center", marginTop: "4rem", fontFamily: "sans-serif" },
  header: { display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" },
  loginBox: { display: "flex", gap: "0.5rem", justifyContent: "center", marginTop: "1rem" },
  input: { padding: "0.5rem 0.75rem", fontSize: "1rem", border: "1px solid #ccc", borderRadius: 6 },
  primaryBtn: {
    padding: "0.6rem 1.5rem",
    background: "#2563eb",
    color: "white",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: "0.95rem",
  },
  secondaryBtn: {
    padding: "0.45rem 1rem",
    background: "white",
    color: "#2563eb",
    border: "1px solid #2563eb",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: "0.9rem",
  },
  logoutBtn: {
    padding: "0.45rem 1rem",
    background: "white",
    color: "#666",
    border: "1px solid #ccc",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: "0.9rem",
    marginLeft: "auto",
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
};
