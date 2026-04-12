import { useState } from "react"
import { apiOrigin } from "@/api/client"
import type { QueueItem, TeacherAction } from "@/api/teacher"
import { postTeacherAction } from "@/api/teacher"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Clock, AlertCircle, CheckCircle2, Lightbulb } from "lucide-react"
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

function parseFeedback(raw: string | object) {
  try {
    return typeof raw === "string" ? JSON.parse(raw) : raw
  } catch {
    return null
  }
}

export default function ReviewCard({ item, onActionComplete }: ReviewCardProps) {
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

  const feedback = parseFeedback(item.ai_feedback)
  const isDeadlineSoon = new Date(item.sla_deadline).getTime() - Date.now() < 3_600_000 * 3

  return (
    <Card className="w-full overflow-hidden">
      {/* 헤더 */}
      <CardHeader className="pb-3 border-b">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-0.5 flex-1 min-w-0">
            <p className="font-bold text-base leading-tight truncate">{item.problem_title}</p>
            <p className="text-sm text-muted-foreground">
              {item.student_name}
              {item.student_id && <span className="ml-1 text-xs opacity-70">({item.student_id})</span>}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5 shrink-0">
            <Badge variant={item.trust_level === "high" ? "success" : "destructive"}>
              신뢰도 {item.trust_level === "high" ? "High" : "Low"}{" "}
              <span className="ml-1 opacity-70">{item.trust_score.toFixed(2)}</span>
            </Badge>
            <Badge variant={item.queue_type === "score_only" ? "warning" : "destructive"} className="text-xs">
              {item.queue_type === "score_only" ? "점수 검토" : "전체 검토"}
            </Badge>
          </div>
        </div>
        <div className={`flex items-center gap-1 text-xs mt-1 ${isDeadlineSoon ? "text-rose-500 font-medium" : "text-muted-foreground"}`}>
          <Clock className="h-3 w-3" />
          <span>SLA {formatDeadline(item.sla_deadline)} 남음</span>
          <span className="mx-1">·</span>
          <span>AI 채점: {item.ai_score > 0 ? "정답" : "오답"}</span>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">

        {/* 문제 본문 */}
        {item.problem_content && (
          <div className="rounded-xl bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 p-3">
            <p className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 mb-1.5 uppercase tracking-wide">문제</p>
            <div className="text-sm leading-relaxed text-foreground">
              {renderMath(item.problem_content)}
            </div>
            {item.problem_answer && (
              <div className="mt-2 pt-2 border-t border-indigo-200 dark:border-indigo-700">
                <span className="text-xs text-indigo-500 mr-1.5">정답:</span>
                <span className="text-sm font-medium">{renderMath(item.problem_answer)}</span>
              </div>
            )}
          </div>
        )}

        {/* 학생 답변 + OCR */}
        <div className={item.ocr_raw_text ? "grid grid-cols-2 gap-3" : ""}>
          <div className="rounded-xl bg-zinc-50 dark:bg-zinc-900 border p-3">
            <p className="text-xs font-semibold text-muted-foreground mb-1.5 uppercase tracking-wide">학생 답변</p>
            {item.input_type === "image" && item.image_path ? (
              <img
                src={`${apiOrigin()}/${item.image_path}`}
                alt="학생 손글씨 풀이"
                className="max-w-full max-h-[300px] rounded-lg border mt-1 object-contain"
              />
            ) : (
              <div className="text-sm leading-relaxed">{renderMath(item.student_answer)}</div>
            )}
          </div>

          {item.ocr_raw_text && (
            <div className="rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 p-3">
              <p className="text-xs font-semibold text-amber-600 dark:text-amber-400 mb-1.5 uppercase tracking-wide">OCR 원문</p>
              <div className="text-sm leading-relaxed text-foreground">{renderMath(item.ocr_raw_text)}</div>
            </div>
          )}
        </div>

        {/* AI 피드백 (항상 표시) */}
        {feedback ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">AI 피드백</p>

            {Array.isArray(feedback.student_mistakes) && feedback.student_mistakes.length > 0 && (
              <div className="rounded-xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-800 p-3 space-y-1.5">
                <div className="flex items-center gap-1.5 mb-1">
                  <AlertCircle className="h-3.5 w-3.5 text-rose-500" />
                  <p className="text-xs font-semibold text-rose-600 dark:text-rose-400">학생 실수</p>
                </div>
                {feedback.student_mistakes.map((m: { step: number; description: string }, i: number) => (
                  <div key={i} className="flex gap-2 text-sm">
                    <span className="text-xs text-rose-400 mt-0.5 shrink-0">Step {m.step}</span>
                    <span className="text-foreground leading-relaxed">{renderMath(m.description)}</span>
                  </div>
                ))}
              </div>
            )}

            {Array.isArray(feedback.correct_approach) && feedback.correct_approach.length > 0 && (
              <div className="rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 p-3 space-y-2">
                <div className="flex items-center gap-1.5 mb-1">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">올바른 풀이</p>
                </div>
                {feedback.correct_approach.map((s: { step: number; title: string; content: string }, i: number) => (
                  <div key={i} className="text-sm">
                    <span className="font-medium text-emerald-700 dark:text-emerald-300">Step {s.step}. {s.title}</span>
                    <div className="text-foreground leading-relaxed mt-0.5">{renderMath(s.content)}</div>
                  </div>
                ))}
              </div>
            )}

            {feedback.key_concept && (
              <div className="rounded-xl bg-sky-50 dark:bg-sky-950/20 border border-sky-200 dark:border-sky-800 p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Lightbulb className="h-3.5 w-3.5 text-sky-500" />
                  <p className="text-xs font-semibold text-sky-600 dark:text-sky-400">핵심 개념</p>
                </div>
                <div className="text-sm text-foreground leading-relaxed">{renderMath(feedback.key_concept)}</div>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl bg-muted/50 p-3 text-sm text-muted-foreground">
            {renderMath(String(item.ai_feedback ?? ""))}
          </div>
        )}

        {/* 수정 폼 */}
        {showModify && (
          <div className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 dark:bg-amber-950/20 p-3">
            <p className="text-xs font-semibold text-amber-700 dark:text-amber-400">수정 내용 입력</p>
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
            className="flex-1 border-emerald-300 text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 font-medium"
            onClick={() => handleAction("approve")}
            disabled={submitting}
          >
            ✓ 승인
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-amber-300 text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-950/30 font-medium"
            onClick={() => handleAction("modify")}
            disabled={submitting || (showModify && (!teacherScore.trim() || !teacherFeedback.trim()))}
          >
            {showModify ? "✎ 수정 제출" : "✎ 수정"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-rose-300 text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/30 font-medium"
            onClick={() => handleAction("reject")}
            disabled={submitting}
          >
            ✕ 거부
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
