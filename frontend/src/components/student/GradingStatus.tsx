// React import not needed with new JSX transform
import type { SubmissionStatusResponse } from "@/api/submissions"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import FeedbackPanel from "./FeedbackPanel"

interface GradingStatusProps {
  result: SubmissionStatusResponse
}

function ScoreBadge({ score, maxScore }: { score: number; maxScore: number | null }) {
  if (score === 0) {
    return <Badge variant="destructive" className="text-base px-3 py-1">오답 (0점)</Badge>
  }
  if (maxScore !== null && score < maxScore) {
    return (
      <Badge variant="warning" className="text-base px-3 py-1">
        부분 정답 ({score}/{maxScore}점)
      </Badge>
    )
  }
  const label = maxScore !== null ? `정답 (${score}/${maxScore}점)` : "정답"
  return <Badge variant="success" className="text-base px-3 py-1">{label}</Badge>
}

export default function GradingStatus({ result }: GradingStatusProps) {
  const hideMistakes = (result.score ?? 0) > 0 || result.solution_status === "correct_solution"
  const feedbackStage =
    result.feedback_status === "running" ? "AI 피드백 생성 중" :
    result.feedback_status === "pending" ? "AI 피드백 대기" :
    result.feedback_status === "failed" ? "AI 피드백 실패" :
    result.feedback_status === "done" ? "AI 피드백 완료" : null
  const hallucinationStage =
    result.hallucination_status === "running" ? "신뢰도 판정 중" :
    result.hallucination_status === "pending" ? "신뢰도 판정 대기" :
    result.hallucination_status === "failed" ? "신뢰도 판정 실패" :
    result.hallucination_status === "done" ? "신뢰도 판정 완료" : null

  if (result.status === "pending" || result.status === "error") {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-64" />
        <p className="text-sm text-muted-foreground">채점 중입니다...</p>
      </div>
    )
  }

  if (result.status === "rejected") {
    return (
      <div className="space-y-2">
        <Badge variant="destructive">거부됨</Badge>
        <p className="text-sm text-muted-foreground">{result.message ?? "채점이 반려되었습니다. 교사에게 문의해주세요."}</p>
      </div>
    )
  }

  // 교사 승인 완료
  if (result.teacher_approved && result.feedback) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          {result.score !== null && (
            <ScoreBadge score={result.score} maxScore={result.max_score} />
          )}
          <Badge variant="default">교사 승인 완료</Badge>
        </div>
        <FeedbackPanel feedback={result.feedback} hideMistakes={hideMistakes} />
      </div>
    )
  }

  if (result.status === "graded") {
    if (result.score_visible && result.score !== null) {
      // 정답+고신뢰도 → 피드백 바로 노출 (교사 검토 전이라도)
      if (result.feedback_visible && result.feedback) {
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <ScoreBadge score={result.score} maxScore={result.max_score} />
            </div>
            <div className="rounded-2xl bg-blue-50 dark:bg-blue-950/30 p-3">
              <p className="text-xs text-blue-700 dark:text-blue-300">
                AI 피드백을 미리 확인할 수 있습니다. 교사 검토 후 최종 확정됩니다.
              </p>
            </div>
            <FeedbackPanel feedback={result.feedback} hideMistakes={hideMistakes} />
          </div>
        )
      }
      // 오답·저신뢰도 → 점수만 표시, 피드백 차단
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            {feedbackStage && <Badge variant="secondary">{feedbackStage}</Badge>}
            {hallucinationStage && <Badge variant="secondary">{hallucinationStage}</Badge>}
          </div>
          <div className="flex items-center gap-3">
            <ScoreBadge score={result.score} maxScore={result.max_score} />
          </div>
          <div className="rounded-2xl bg-muted p-3">
            <p className="text-sm text-muted-foreground">
              {result.score === 0
                ? "오답입니다. 교사 검토 후 상세 피드백을 확인할 수 있습니다."
                : "교사 검토 대기 중입니다. 피드백은 검토 후 확인할 수 있습니다."}
            </p>
          </div>
        </div>
      )
    }
    return (
      <div className="rounded-2xl bg-muted p-4">
        <p className="text-sm text-muted-foreground">검토 중입니다. 결과는 잠시 후 확인할 수 있습니다.</p>
      </div>
    )
  }

  if (result.status === "approved") {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="success">{result.auto_approved ? "자동 승인 완료" : "승인 완료"}</Badge>
        </div>
        {result.score !== null && (
          <ScoreBadge score={result.score} maxScore={result.max_score} />
        )}
        {result.feedback ? (
          <FeedbackPanel feedback={result.feedback} hideMistakes={hideMistakes} />
        ) : (
          <p className="text-sm text-muted-foreground">피드백을 불러오는 중입니다.</p>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-2xl bg-muted p-4">
      <p className="text-sm text-muted-foreground">{result.message ?? "채점 중입니다."}</p>
    </div>
  )
}
