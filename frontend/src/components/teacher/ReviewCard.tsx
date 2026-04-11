import { useState } from "react"
import type { QueueItem, TeacherAction } from "@/api/teacher"
import { postTeacherAction } from "@/api/teacher"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { ChevronDown, ChevronUp, Clock } from "lucide-react"
import { renderMath } from "@/lib/renderMath"

interface ReviewCardProps {
  item: QueueItem
  onActionComplete: () => void
}

function formatDeadline(deadline: string): string {
  const diff = new Date(deadline).getTime() - Date.now()
  if (diff <= 0) return "마감"
  const hours = Math.floor(diff / 3_600_000)
  const minutes = Math.floor((diff % 3_600_000) / 60_000)
  return `${hours}시간 ${minutes}분`
}

export default function ReviewCard({ item, onActionComplete }: ReviewCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [showModify, setShowModify] = useState(false)
  const [teacherScore, setTeacherScore] = useState("")
  const [teacherFeedback, setTeacherFeedback] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleAction(action: TeacherAction) {
    if (action === "modify" && !showModify) {
      setShowModify(true)
      return
    }
    if (action === "modify" && (!teacherScore.trim() || !teacherFeedback.trim())) return

    setSubmitting(true)
    setError(null)
    try {
      const payload =
        action === "modify"
          ? { action, teacher_score: Number(teacherScore), teacher_feedback: teacherFeedback }
          : { action }
      await postTeacherAction(item.queue_id, payload)
      onActionComplete()
    } catch (e) {
      setError(e instanceof Error ? e.message : "액션 제출 실패")
    } finally {
      setSubmitting(false)
    }
  }

  let feedbackText = ""
  try {
    const parsed = typeof item.ai_feedback === "string" ? JSON.parse(item.ai_feedback) : item.ai_feedback
    if (parsed?.student_mistakes?.length > 0) {
      feedbackText = parsed.student_mistakes.map((m: { description: string }) => m.description).join(" / ")
    } else if (parsed?.key_concept) {
      feedbackText = parsed.key_concept
    }
  } catch {
    feedbackText = String(item.ai_feedback ?? "")
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1">
            <p className="font-semibold text-base">{item.problem_title}</p>
            <p className="text-sm text-muted-foreground">
              {item.student_name}
              {item.student_id && <span className="ml-1 text-xs">({item.student_id})</span>}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Badge variant={item.trust_level === "high" ? "success" : "destructive"}>
              {item.trust_level === "high" ? "신뢰도 High" : "신뢰도 Low"}{" "}
              <span className="ml-1 opacity-70">{item.trust_score.toFixed(2)}</span>
            </Badge>
            <Badge variant={item.queue_type === "score_only" ? "warning" : "destructive"} className="text-xs">
              {item.queue_type === "score_only" ? "점수 검토" : "전체 검토"}
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1">
          <Clock className="h-3 w-3" />
          <span>SLA {formatDeadline(item.sla_deadline)} 남음</span>
          <span className="mx-1">·</span>
          <span>AI 점수 {item.ai_score}점</span>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 학생 답변 */}
        <div className="rounded-xl bg-muted p-3">
          <p className="text-xs font-medium text-muted-foreground mb-1">학생 답변</p>
          {item.input_type === "image" && item.image_path ? (
            <img
              src={`http://localhost:8000/${item.image_path}`}
              alt="학생 손글씨 풀이"
              className="max-w-full rounded-lg border mt-1"
              style={{ maxHeight: "400px", objectFit: "contain" }}
            />
          ) : (
            <div className="text-sm leading-relaxed">{renderMath(item.student_answer)}</div>
          )}
        </div>

        {/* AI 피드백 토글 */}
        <button
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          AI 피드백 {expanded ? "접기" : "보기"}
        </button>
        {expanded && (
          <div className="rounded-xl border p-3 text-sm text-muted-foreground leading-relaxed">
            {renderMath(feedbackText || String(item.ai_feedback))}
          </div>
        )}

        {/* 수정 폼 */}
        {showModify && (
          <div className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 dark:bg-amber-950/20 p-3">
            <p className="text-xs font-medium text-amber-700 dark:text-amber-400">수정 내용 입력</p>
            <div className="flex items-center gap-2">
              <label className="text-sm whitespace-nowrap">확정 점수</label>
              <Input
                type="number"
                min={0}
                value={teacherScore}
                onChange={(e) => setTeacherScore(e.target.value)}
                className="w-24"
                placeholder="점수"
              />
              <span className="text-sm">점</span>
            </div>
            <Textarea
              rows={4}
              placeholder="수정된 피드백을 입력하세요..."
              value={teacherFeedback}
              onChange={(e) => setTeacherFeedback(e.target.value)}
            />
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {/* 액션 버튼 */}
        <div className="flex gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-emerald-300 text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/30"
            onClick={() => handleAction("approve")}
            disabled={submitting}
          >
            승인
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-amber-300 text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-950/30"
            onClick={() => handleAction("modify")}
            disabled={submitting || (showModify && (!teacherScore.trim() || !teacherFeedback.trim()))}
          >
            {showModify ? "수정 제출" : "수정"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-rose-300 text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/30"
            onClick={() => handleAction("reject")}
            disabled={submitting}
          >
            거부
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
