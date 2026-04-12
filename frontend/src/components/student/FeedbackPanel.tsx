import { renderMath } from "@/lib/renderMath"
import type { Feedback } from "@/api/submissions"
import { AlertPanel } from "@/components/ui/alert-panel"
import { AlertCircle, CheckCircle2, Lightbulb } from "lucide-react"

interface FeedbackPanelProps {
  feedback: Feedback
}

export default function FeedbackPanel({ feedback }: FeedbackPanelProps) {
  return (
    <div className="space-y-4 mt-4">
      {feedback.student_mistakes.length > 0 && (
        <AlertPanel tone="error" icon={AlertCircle} title="틀린 부분" className="space-y-2">
          <ul className="space-y-1">
            {feedback.student_mistakes.map((m) => (
              <li key={m.step} className="text-sm text-red-800 dark:text-red-200">
                <span className="font-medium">단계 {m.step}:</span>{" "}
                {renderMath(m.description)}
              </li>
            ))}
          </ul>
        </AlertPanel>
      )}

      {feedback.correct_approach.length > 0 && (
        <AlertPanel tone="success" icon={CheckCircle2} title="올바른 풀이" className="space-y-3">
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
        </AlertPanel>
      )}

      {feedback.key_concept && (
        <AlertPanel tone="info" icon={Lightbulb} title="핵심 개념">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            {renderMath(feedback.key_concept)}
          </p>
        </AlertPanel>
      )}
    </div>
  )
}
