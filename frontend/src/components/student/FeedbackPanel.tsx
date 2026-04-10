import * as React from "react"
import { InlineMath, BlockMath } from "react-katex"
import "katex/dist/katex.min.css"
import type { Feedback } from "@/api/submissions"

interface FeedbackPanelProps {
  feedback: Feedback
}

function renderWithKatex(text: string): React.ReactNode {
  const parts = text.split(/(\$\$[\s\S]+?\$\$|\$[^$]+?\$)/g)
  return parts.map((part, i) => {
    if (part.startsWith("$$") && part.endsWith("$$")) {
      return <BlockMath key={i} math={part.slice(2, -2)} />
    }
    if (part.startsWith("$") && part.endsWith("$")) {
      return <InlineMath key={i} math={part.slice(1, -1)} />
    }
    return <span key={i}>{part}</span>
  })
}

export default function FeedbackPanel({ feedback }: FeedbackPanelProps) {
  return (
    <div className="space-y-4 mt-4">
      {feedback.student_mistakes.length > 0 && (
        <div className="rounded-2xl bg-rose-50 dark:bg-rose-950/30 p-4 space-y-2">
          <h4 className="text-sm font-semibold text-rose-700 dark:text-rose-300">틀린 부분</h4>
          <ul className="space-y-1">
            {feedback.student_mistakes.map((m) => (
              <li key={m.step} className="text-sm text-rose-800 dark:text-rose-200">
                <span className="font-medium">단계 {m.step}:</span>{" "}
                {renderWithKatex(m.description)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {feedback.correct_approach.length > 0 && (
        <div className="rounded-2xl bg-indigo-50 dark:bg-indigo-950/30 p-4 space-y-3">
          <h4 className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">올바른 풀이</h4>
          <ol className="space-y-2">
            {feedback.correct_approach.map((s) => (
              <li key={s.step} className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-600 text-white text-xs flex items-center justify-center font-semibold">
                  {s.step}
                </span>
                <div className="text-sm text-indigo-800 dark:text-indigo-200">
                  <strong>{s.title}:</strong>{" "}
                  {renderWithKatex(s.content)}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {feedback.key_concept && (
        <div className="rounded-2xl bg-amber-50 dark:bg-amber-950/30 p-4">
          <h4 className="text-sm font-semibold text-amber-700 dark:text-amber-300 mb-1">핵심 개념</h4>
          <p className="text-sm text-amber-800 dark:text-amber-200">
            {renderWithKatex(feedback.key_concept)}
          </p>
        </div>
      )}
    </div>
  )
}
