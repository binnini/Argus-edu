import type { SubmissionOverviewItem } from "@/api/teacher"
import { apiOrigin } from "@/api/client"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { renderMath } from "@/lib/renderMath"

interface SubmissionDetailDialogProps {
  item: SubmissionOverviewItem | null
  open: boolean
  onClose: () => void
}

function statusLabel(status: string) {
  switch (status) {
    case "pending": return { label: "채점 중", variant: "secondary" as const }
    case "graded": return { label: "검토 대기", variant: "warning" as const }
    case "approved": return { label: "승인 완료", variant: "success" as const }
    case "rejected": return { label: "거부", variant: "destructive" as const }
    default: return { label: status, variant: "secondary" as const }
  }
}

function inputTypeLabel(type: string) {
  switch (type) {
    case "text": return "텍스트 입력"
    case "image": return "이미지 업로드"
    case "canvas": return "직접 그리기"
    default: return type
  }
}

export default function SubmissionDetailDialog({ item, open, onClose }: SubmissionDetailDialogProps) {
  if (!item) return null

  const { label, variant } = statusLabel(item.status)

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="text-base leading-snug">{renderMath(item.problem_title)}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          {/* 학생 정보 */}
          <div className="flex flex-wrap gap-2 items-center">
            <span className="font-medium">{item.student_name}</span>
            {item.student_id && (
              <span className="text-muted-foreground text-xs">({item.student_id})</span>
            )}
            <Badge variant="secondary" className="text-xs">{inputTypeLabel(item.input_type)}</Badge>
            <Badge variant={variant} className="text-xs">{label}</Badge>
          </div>

          {/* 제출 답변 */}
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">제출 답변</p>
            {item.input_type === "image" && item.image_path ? (
              <img
                src={`${apiOrigin()}/${item.image_path}`}
                alt="학생 제출 이미지"
                className="max-w-full max-h-[400px] rounded-xl border object-contain"
              />
            ) : (
              <div className="rounded-xl bg-muted/50 p-3 text-sm leading-relaxed whitespace-pre-wrap">
                {item.student_answer ?? "—"}
              </div>
            )}
          </div>

          {/* 점수 정보 */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-muted p-3">
              <p className="text-xs text-muted-foreground mb-1">AI 점수</p>
              <p className="font-semibold">{item.ai_score !== null ? `${item.ai_score}점` : "—"}</p>
            </div>
            <div className="rounded-xl bg-muted p-3">
              <p className="text-xs text-muted-foreground mb-1">최종 점수</p>
              <p className="font-semibold">{item.final_score !== null ? `${item.final_score}점` : "—"}</p>
            </div>
          </div>

          {/* 신뢰도 */}
          {item.trust_level && (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">신뢰도</span>
              <Badge variant={item.trust_level === "high" ? "success" : "destructive"}>
                {item.trust_level === "high" ? "High" : "Low"}
              </Badge>
            </div>
          )}

          {/* 시각 정보 */}
          <div className="space-y-1 text-xs text-muted-foreground">
            <p>제출: {new Date(item.submitted_at).toLocaleString("ko-KR")}</p>
            {item.reviewed_at && (
              <p>검토: {new Date(item.reviewed_at).toLocaleString("ko-KR")}</p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
