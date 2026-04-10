// React import not needed with new JSX transform
import type { SubmissionStatusResponse } from "@/api/submissions"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import FeedbackPanel from "./FeedbackPanel"

interface GradingStatusProps {
  result: SubmissionStatusResponse
}

export default function GradingStatus({ result }: GradingStatusProps) {
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

  if (result.teacher_approved && result.feedback) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          {result.score !== null && (
            <Badge variant="success" className="text-base px-3 py-1">
              {result.score}점
            </Badge>
          )}
          <Badge variant="default">교사 승인 완료</Badge>
        </div>
        <FeedbackPanel feedback={result.feedback} />
      </div>
    )
  }

  if (result.status === "graded") {
    if (result.score_visible && result.score !== null) {
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <Badge variant="success" className="text-base px-3 py-1">{result.score}점</Badge>
          </div>
          <div className="rounded-2xl bg-muted p-3">
            <p className="text-sm text-muted-foreground">교사 검토 대기 중입니다. 피드백은 검토 후 확인할 수 있습니다.</p>
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
        {result.score !== null && (
          <Badge variant="success" className="text-base px-3 py-1">{result.score}점</Badge>
        )}
        {result.feedback ? (
          <FeedbackPanel feedback={result.feedback} />
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
