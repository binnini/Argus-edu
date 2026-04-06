import { useState } from "react";
import {
  QueueItem,
  TeacherAction,
  submitTeacherAction,
} from "../api/teacher";

interface ReviewCardProps {
  item: QueueItem;
  password: string;
  onSuccess: () => void;
  onBack: () => void;
}

export default function ReviewCard({ item, password, onSuccess, onBack }: ReviewCardProps) {
  const [action, setAction] = useState<TeacherAction>("approve");
  const [teacherScore, setTeacherScore] = useState("");
  const [teacherExplanation, setTeacherExplanation] = useState(item.ai_explanation);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const payload =
        action === "modify"
          ? {
              action,
              teacher_score: Number(teacherScore),
              teacher_explanation: teacherExplanation,
            }
          : { action };

      await submitTeacherAction(item.queue_id, payload, password);
      onSuccess();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "액션 제출 실패");
    } finally {
      setSubmitting(false);
    }
  }

  const submitDisabled =
    submitting ||
    (action === "modify" && (!teacherScore.trim() || !teacherExplanation.trim()));

  return (
    <div style={styles.container}>
      <button style={styles.backBtn} onClick={onBack}>
        ← 목록으로
      </button>

      <h2 style={{ marginTop: "1rem" }}>{item.problem_title}</h2>

      <div style={styles.infoRow}>
        <TrustBadge level={item.trust_level} score={item.trust_score} />
        <span style={styles.metaText}>AI 점수: {item.ai_score}점</span>
        <span style={styles.metaText}>
          SLA 마감: {new Date(item.sla_deadline).toLocaleString("ko-KR")} (
          {formatDeadline(item.sla_deadline)} 남음)
        </span>
      </div>

      <Section title="학생 답변">
        <div style={styles.contentBox}>{item.student_answer}</div>
      </Section>

      <Section title="AI 풀이 설명">
        <div style={styles.contentBox}>{item.ai_explanation}</div>
      </Section>

      <Section title="액션 선택">
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
      </Section>

      {action === "modify" && (
        <Section title="수정 내용">
          <div style={styles.modifyForm}>
            <label style={styles.fieldLabel}>
              교사 확정 점수
              <input
                type="number"
                value={teacherScore}
                onChange={(e) => setTeacherScore(e.target.value)}
                style={{ ...styles.input, width: 100, marginLeft: "0.5rem" }}
                min={0}
                placeholder="점수 입력"
              />
            </label>
            <label style={styles.fieldLabel}>
              수정 풀이 설명
              <textarea
                value={teacherExplanation}
                onChange={(e) => setTeacherExplanation(e.target.value)}
                style={{ ...styles.textarea, marginTop: "0.4rem" }}
                rows={6}
                placeholder="수정된 풀이 설명을 입력하세요..."
              />
            </label>
          </div>
        </Section>
      )}

      {error && <p style={{ color: "red" }}>{error}</p>}

      <button
        style={{
          ...styles.primaryBtn,
          marginTop: "1rem",
          opacity: submitDisabled ? 0.6 : 1,
        }}
        onClick={handleSubmit}
        disabled={submitDisabled}
      >
        {submitting ? "제출 중..." : "제출"}
      </button>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "1.25rem" }}>
      <h3 style={{ marginBottom: "0.4rem", fontSize: "1rem" }}>{title}</h3>
      {children}
    </div>
  );
}

function TrustBadge({ level, score }: { level: "high" | "low"; score: number }) {
  return (
    <span
      style={{
        background: level === "high" ? "#d1fae5" : "#fee2e2",
        color: level === "high" ? "#065f46" : "#991b1b",
        borderRadius: 4,
        padding: "2px 10px",
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
  container: {
    maxWidth: 800,
    margin: "2rem auto",
    padding: "0 1rem",
    fontFamily: "sans-serif",
  },
  backBtn: {
    background: "none",
    border: "1px solid #ccc",
    borderRadius: 6,
    padding: "0.4rem 0.8rem",
    cursor: "pointer",
    fontSize: "0.9rem",
  },
  infoRow: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    marginBottom: "1.25rem",
    flexWrap: "wrap",
  },
  metaText: { fontSize: "0.9rem", color: "#555" },
  contentBox: {
    background: "#f9f9f9",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    padding: "1rem",
    whiteSpace: "pre-wrap",
    fontSize: "0.95rem",
  },
  actionGroup: { display: "flex", gap: "1.5rem" },
  actionLabel: {
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    cursor: "pointer",
    fontSize: "0.95rem",
  },
  modifyForm: {
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  fieldLabel: {
    display: "flex",
    alignItems: "flex-start",
    flexDirection: "column" as const,
    fontSize: "0.9rem",
    fontWeight: "500",
  },
  input: {
    padding: "0.5rem 0.75rem",
    fontSize: "1rem",
    border: "1px solid #ccc",
    borderRadius: 6,
  },
  textarea: {
    width: "100%",
    padding: "0.5rem",
    fontSize: "0.95rem",
    border: "1px solid #ccc",
    borderRadius: 6,
    boxSizing: "border-box" as const,
  },
  primaryBtn: {
    padding: "0.65rem 2rem",
    background: "#2563eb",
    color: "white",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: "1rem",
  },
};
