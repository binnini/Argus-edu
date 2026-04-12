import { renderMath } from "@/lib/renderMath"
import type { Feedback } from "@/api/submissions"

interface FeedbackPanelProps {
  feedback: Feedback
}

export default function FeedbackPanel({ feedback }: FeedbackPanelProps) {
  return (
    <div className="space-y-4 mt-4">
      {feedback.student_mistakes.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 space-y-2 dark:border-red-800 dark:bg-red-950/30">
          <h4 className="text-sm font-semibold text-red-700 dark:text-red-300">틀린 부분</h4>
          <ul className="space-y-1">
            {feedback.student_mistakes.map((m) => (
              <li key={m.step} className="text-sm text-red-800 dark:text-red-200">
                <span className="font-medium">단계 {m.step}:</span>{" "}
                {renderMath(m.description)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback.correct_approach.length > 0 && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 space-y-3 dark:border-green-800 dark:bg-green-950/30">
          <h4 className="text-sm font-semibold text-green-700 dark:text-green-300">올바른 풀이</h4>
          <ol className="space-y-2">
            {feedback.correct_approach.map((s) => (
              <li key={s.step} className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-green-600 text-white text-xs flex items-center justify-center font-semibold">
                  {s.step}
                </span>
                <div className="text-sm text-green-800 dark:text-green-200">
                  <strong>{s.title}:</strong>{" "}
                  {renderMath(s.content)}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {feedback.key_concept && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950/30">
          <h4 className="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-1">핵심 개념</h4>
          <p className="text-sm text-blue-800 dark:text-blue-200">
            {renderMath(feedback.key_concept)}
          </p>
        </div>
      )}
    </div>
  )
}
