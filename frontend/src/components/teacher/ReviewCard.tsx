import { useState } from "react"
import { apiOrigin } from "@/api/client"
import type { QueueItem, TeacherAction } from "@/api/teacher"
import { postTeacherAction } from "@/api/teacher"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Clock, AlertCircle, CheckCircle2, ChevronDown, ExternalLink, ImageIcon, Lightbulb } from "lucide-react"
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

function scoreTone(score: number): string {
  if (score <= 0) return "text-red-700 bg-red-50 border-red-200 dark:text-red-300 dark:bg-red-950/30 dark:border-red-800"
  return "text-green-700 bg-green-50 border-green-200 dark:text-green-300 dark:bg-green-950/30 dark:border-green-800"
}

function parseFeedback(raw: string | object) {
  try {
    return typeof raw === "string" ? JSON.parse(raw) : raw
  } catch {
    return null
  }
}

function extractFinalAnswer(studentAnswer: string | null | undefined): string | null {
  if (!studentAnswer) return null
  const m = studentAnswer.match(/\[최종 답\]\s*(.+?)(?:\n|$)/)
  if (!m) return null
  const value = m[1]?.trim()
  return value ? value : null
}

export default function ReviewCard({ item, onActionComplete }: ReviewCardProps) {
  const [showModify, setShowModify] = useState(false)
  const [teacherScore, setTeacherScore] = useState("")
  const [teacherFeedback, setTeacherFeedback] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showProblem, setShowProblem] = useState(false)

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
  const finalAnswer = extractFinalAnswer(item.student_answer)
  const isDeadlineSoon = new Date(item.sla_deadline).getTime() - Date.now() < 3_600_000 * 3
  const imageUrl = item.image_path ? `${apiOrigin()}/${item.image_path}` : null
  const isReviewed = !!item.action

  return (
    <Card className="w-full overflow-hidden">
      {/* 헤더 */}
      <CardHeader className="pb-3 border-b border-gray-200">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-0.5 flex-1 min-w-0">
            <p className="font-bold text-base leading-tight truncate text-gray-900 dark:text-gray-50">{item.problem_title}</p>
            <p className="text-sm text-muted-foreground">
              {item.student_name}
              {item.student_id && <span className="ml-1 text-xs opacity-70">({item.student_id})</span>}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5 shrink-0">
            {isReviewed && (
              <Badge variant="secondary">
                처리 완료: {item.auto_approved ? "자동 승인" : item.action === "approve" ? "승인" : item.action === "modify" ? "수정" : "거부"}
              </Badge>
            )}
            <Badge variant={item.trust_level === "high" ? "success" : "destructive"}>
              신뢰도 {item.trust_level === "high" ? "High" : "Low"}{" "}
              <span className="ml-1 opacity-70">{item.trust_score.toFixed(2)}</span>
            </Badge>
            <Badge variant={item.queue_type === "score_only" ? "warning" : "destructive"} className="text-xs">
              {item.queue_type === "score_only" ? "점수 검토" : "전체 검토"}
            </Badge>
          </div>
        </div>
          <div className="mt-3 grid gap-2 rounded-lg border border-gray-200 bg-gray-50 p-2 text-xs dark:border-zinc-800 dark:bg-zinc-900 sm:grid-cols-4">
          <div className={`rounded-md border px-2.5 py-2 font-semibold ${scoreTone(item.ai_score)}`}>
            AI {item.ai_score}점
          </div>
          <div className="rounded-md border border-gray-200 bg-white px-2.5 py-2 dark:border-zinc-800 dark:bg-card">
            <span className="text-muted-foreground">신뢰도 </span>
            <span className={item.trust_level === "high" ? "font-semibold text-green-700" : "font-semibold text-red-700"}>
              {item.trust_level === "high" ? "High" : "Low"}
            </span>
          </div>
            <div className="rounded-md border border-gray-200 bg-white px-2.5 py-2 dark:border-zinc-800 dark:bg-card">
              {item.queue_type === "score_only" ? "점수 검토" : "전체 검토"}
            </div>
            <div className="rounded-md border border-gray-200 bg-white px-2.5 py-2 dark:border-zinc-800 dark:bg-card">
              피드백: {item.feedback_status === "running" ? "생성 중" : item.feedback_status === "pending" ? "대기" : item.feedback_status === "done" ? "완료" : item.feedback_status === "failed" ? "실패" : "—"}
            </div>
            <div className="rounded-md border border-gray-200 bg-white px-2.5 py-2 dark:border-zinc-800 dark:bg-card">
              신뢰도: {item.hallucination_status === "running" ? "판정 중" : item.hallucination_status === "pending" ? "대기" : item.hallucination_status === "done" ? "완료" : item.hallucination_status === "failed" ? "실패" : "—"}
            </div>
            <div className={`flex items-center gap-1 rounded-md border px-2.5 py-2 ${isDeadlineSoon ? "border-rose-200 bg-rose-50 font-semibold text-rose-600 dark:border-rose-800 dark:bg-rose-950/30" : "border-gray-200 bg-white text-muted-foreground dark:border-zinc-800 dark:bg-card"}`}>
              <Clock className="h-3 w-3" />
              SLA {formatDeadline(item.sla_deadline)}
            </div>
          </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">

        {/* 문제 본문 */}
        {item.problem_content && (
          <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold text-blue-700 dark:text-blue-400 uppercase tracking-wide">문제</p>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-blue-700 hover:bg-blue-100 dark:text-blue-300 dark:hover:bg-blue-950/50"
                onClick={() => setShowProblem((v) => !v)}
              >
                {showProblem ? "접기" : "보기"}
                <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showProblem ? "rotate-180" : ""}`} />
              </Button>
            </div>
            {showProblem && (
              <div className="mt-2">
                <div className="text-sm leading-relaxed text-foreground">
                  {renderMath(item.problem_content)}
                </div>
                {item.problem_answer && (
                  <div className="mt-2 pt-2 border-t border-blue-200 dark:border-blue-700">
                    <span className="text-xs text-blue-600 mr-1.5">정답:</span>
                    <span className="text-sm font-medium">{renderMath(item.problem_answer)}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 학생 답변 + OCR 결과 */}
        <div className="rounded-lg bg-gray-50 p-4 dark:bg-zinc-900">
          <div className="mb-3 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 dark:border-indigo-800 dark:bg-indigo-950/30">
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">학생 제출 답</p>
            <div className="mt-1 text-sm leading-relaxed text-foreground">
              {finalAnswer ? renderMath(finalAnswer) : (item.student_answer ? renderMath(item.student_answer) : "—")}
            </div>
          </div>
          <div className={item.input_type === "image" ? "grid gap-4 md:grid-cols-2" : ""}>
            <div className="rounded-lg border border-gray-200 bg-white p-3 dark:bg-card">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-200">
                  {item.input_type === "image" && <ImageIcon className="h-3.5 w-3.5 text-gray-400" />}
                  학생 답변
                </p>
                {imageUrl && (
                  <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
                    <a href={imageUrl} target="_blank" rel="noreferrer">
                      원본 보기
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </Button>
                )}
              </div>
              {item.input_type === "image" && imageUrl ? (
                <div className="flex min-h-[260px] items-center justify-center rounded-lg border bg-gray-50 p-2">
                  <img
                    src={imageUrl}
                    alt="학생 손글씨 풀이"
                    className="max-h-[300px] max-w-full object-contain"
                  />
                </div>
              ) : (
                <div className="text-sm leading-relaxed">{renderMath(item.student_answer)}</div>
              )}
            </div>

            {item.input_type === "image" && (
              <div className="rounded-lg border border-gray-200 bg-white p-3 dark:bg-card">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-200">OCR 결과</p>
                  <Badge variant="secondary" className="text-xs">채점 사용</Badge>
                </div>
                <div className={`min-h-[260px] rounded-lg border p-3 text-sm leading-relaxed whitespace-pre-wrap ${item.ocr_raw_text ? "border-gray-200 bg-gray-50 text-foreground" : "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300"}`}>
                  {item.ocr_raw_text ? renderMath(item.ocr_raw_text) : (
                    <div className="flex items-start gap-2">
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                      <span>OCR 결과가 없습니다. 원본 이미지를 기준으로 검토해 주세요.</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* AI 피드백 (항상 표시) */}
        {feedback ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">AI 피드백</p>

            {Array.isArray(feedback.student_mistakes) && feedback.student_mistakes.length > 0 && (
              <div className="rounded-lg bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 p-3 space-y-1.5">
                <div className="flex items-center gap-1.5 mb-1">
                  <AlertCircle className="h-3.5 w-3.5 text-red-500" />
                  <p className="text-xs font-semibold text-red-700 dark:text-red-400">학생 실수</p>
                </div>
                {feedback.student_mistakes.map((m: { step: number; description: string }, i: number) => (
                  <div key={i} className="flex gap-2 text-sm">
                    <span className="text-xs text-red-600 mt-0.5 shrink-0">Step {m.step}</span>
                    <span className="text-foreground leading-relaxed">{renderMath(m.description)}</span>
                  </div>
                ))}
              </div>
            )}

            {Array.isArray(feedback.correct_approach) && feedback.correct_approach.length > 0 && (
              <div className="rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 p-3 space-y-2">
                <div className="flex items-center gap-1.5 mb-1">
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                  <p className="text-xs font-semibold text-green-700 dark:text-green-400">올바른 풀이</p>
                </div>
                {feedback.correct_approach.map((s: { step: number; title: string; content: string }, i: number) => (
                  <div key={i} className="text-sm">
                    <span className="font-medium text-green-700 dark:text-green-300">Step {s.step}. {s.title}</span>
                    <div className="text-foreground leading-relaxed mt-0.5">{renderMath(s.content)}</div>
                  </div>
                ))}
              </div>
            )}

            {feedback.key_concept && (
              <div className="rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Lightbulb className="h-3.5 w-3.5 text-blue-500" />
                  <p className="text-xs font-semibold text-blue-700 dark:text-blue-400">핵심 개념</p>
                </div>
                <div className="text-sm text-foreground leading-relaxed">{renderMath(feedback.key_concept)}</div>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
            {renderMath(String(item.ai_feedback ?? ""))}
          </div>
        )}

        {/* 수정 폼 */}
        {showModify && (
          <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/20 p-3">
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
        {!isReviewed ? (
          <div className="grid grid-cols-2 gap-2 border-t border-gray-200 pt-4 sm:grid-cols-[1fr_auto_auto]">
            <Button
              variant="default"
              size="sm"
              className="col-span-2 bg-primary text-primary-foreground hover:bg-primary/90 sm:col-span-1 sm:min-w-44"
              onClick={() => handleAction("approve")}
              disabled={submitting}
            >
              승인하기
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="border-gray-300 px-5 text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-zinc-900"
              onClick={() => handleAction("modify")}
              disabled={submitting || (showModify && (!teacherScore.trim() || !teacherFeedback.trim()))}
            >
              {showModify ? "수정 제출" : "수정"}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              className="px-5"
              onClick={() => handleAction("reject")}
              disabled={submitting}
            >
              거부
            </Button>
          </div>
        ) : (
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-muted-foreground">
            {item.reviewed_at
              ? `검토 완료: ${new Date(item.reviewed_at).toLocaleString("ko-KR")}`
              : "검토 완료"}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
