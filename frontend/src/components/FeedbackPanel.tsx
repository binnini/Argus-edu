import { Feedback } from "../api/submissions";

interface FeedbackPanelProps {
  feedback: Feedback;
}

/**
 * 개인화 피드백 패널.
 * 절대 제약: teacher_approved === true일 때만 렌더링 (호출 측에서 보장).
 */
export default function FeedbackPanel({ feedback }: FeedbackPanelProps) {
  return (
    <div style={styles.panel}>
      <h3 style={styles.panelTitle}>개인화 피드백</h3>

      {/* 학생 오류 분석 */}
      {feedback.student_mistakes.length > 0 && (
        <section style={styles.section}>
          <h4 style={styles.sectionTitle}>❌ 틀린 부분 분석</h4>
          <ul style={styles.mistakeList}>
            {feedback.student_mistakes.map((m, i) => (
              <li key={i} style={styles.mistakeItem}>
                <span style={styles.stepBadge}>{m.step}단계</span>
                <span>{m.description}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 올바른 풀이 방향 */}
      {feedback.correct_approach.length > 0 && (
        <section style={styles.section}>
          <h4 style={styles.sectionTitle}>✅ 올바른 풀이 방향</h4>
          <ol style={styles.approachList}>
            {feedback.correct_approach.map((s) => (
              <li key={s.step} style={styles.approachItem}>
                <div style={styles.approachTitle}>
                  {s.step}단계: {s.title}
                </div>
                <div style={styles.approachContent}>{s.content}</div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* 핵심 개념 */}
      {feedback.key_concept && (
        <section style={styles.conceptBox}>
          <span style={styles.conceptLabel}>💡 핵심 개념</span>
          <p style={styles.conceptText}>{feedback.key_concept}</p>
        </section>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    background: "#f0fdf4",
    border: "1px solid #86efac",
    borderRadius: 10,
    padding: "1.5rem",
    marginTop: "1rem",
  },
  panelTitle: {
    margin: "0 0 1rem",
    color: "#166534",
    fontSize: "1.1rem",
  },
  section: {
    marginBottom: "1.25rem",
  },
  sectionTitle: {
    margin: "0 0 0.5rem",
    fontSize: "0.95rem",
    color: "#374151",
  },
  mistakeList: {
    listStyle: "none",
    padding: 0,
    margin: 0,
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
  },
  mistakeItem: {
    display: "flex",
    alignItems: "flex-start",
    gap: "0.5rem",
    background: "#fff1f2",
    border: "1px solid #fda4af",
    borderRadius: 6,
    padding: "0.5rem 0.75rem",
    fontSize: "0.9rem",
  },
  stepBadge: {
    background: "#e11d48",
    color: "white",
    borderRadius: 4,
    padding: "1px 6px",
    fontSize: "0.75rem",
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },
  approachList: {
    paddingLeft: "1.25rem",
    margin: 0,
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  approachItem: {
    background: "white",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    padding: "0.75rem",
  },
  approachTitle: {
    fontWeight: 600,
    fontSize: "0.9rem",
    marginBottom: "0.25rem",
    color: "#1e40af",
  },
  approachContent: {
    fontSize: "0.9rem",
    color: "#374151",
    lineHeight: 1.6,
    whiteSpace: "pre-wrap" as const,
  },
  conceptBox: {
    background: "#fefce8",
    border: "1px solid #fde047",
    borderRadius: 8,
    padding: "0.75rem 1rem",
  },
  conceptLabel: {
    fontWeight: 600,
    fontSize: "0.85rem",
    color: "#713f12",
    display: "block",
    marginBottom: "0.25rem",
  },
  conceptText: {
    margin: 0,
    fontSize: "0.9rem",
    color: "#374151",
    lineHeight: 1.6,
  },
};
