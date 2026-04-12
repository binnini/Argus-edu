// Student homework problem picker.

import { getProblem, type Problem, type StudentHomeworkItem } from "@/api/submissions"
import { Badge } from "@/components/ui/badge"
import { FolderOpen } from "lucide-react"

interface HomeworkTabProps {
  homework: StudentHomeworkItem[]
  homeworkLoading: boolean
  setHomeworkLoading: (loading: boolean) => void
  onSelectProblem: (problem: Problem) => void
}

function formatDueDate(due: string | null): { text: string; overdue: boolean } | null {
  if (!due) return null
  const d = new Date(due)
  const now = new Date()
  const overdue = d < now
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  const dd = String(d.getDate()).padStart(2, "0")
  return { text: `${mm}/${dd} 마감`, overdue }
}

export default function HomeworkTab({
  homework,
  homeworkLoading,
  setHomeworkLoading,
  onSelectProblem,
}: HomeworkTabProps) {
  if (homeworkLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-6 justify-center">
        <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        불러오는 중...
      </div>
    )
  }
  if (homework.length === 0) {
    return (
      <div className="flex min-h-48 flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 bg-gray-50 px-6 py-10 text-center">
        <FolderOpen className="h-12 w-12 text-gray-300" />
        <p className="mt-3 text-sm font-semibold text-gray-900">할당된 숙제가 없습니다</p>
        <p className="mt-1 text-xs text-gray-500">선생님이 숙제를 할당할 때까지 기다려주세요</p>
      </div>
    )
  }
  return (
    <div className="space-y-6">
      {homework.map((hw) => {
        const dueFmt = formatDueDate(hw.due_date)
        return (
          <div key={hw.homework_id}>
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-50">{hw.title}</h3>
                {hw.group_name && (
                  <span className="text-xs text-muted-foreground">{hw.group_name}</span>
                )}
              </div>
              <div className="text-right">
                <span className="text-xs font-mono text-muted-foreground">
                  {hw.completed_problems}/{hw.total_problems}
                </span>
                {dueFmt && (
                  <p className={`text-xs ${dueFmt.overdue ? "text-destructive" : "text-muted-foreground"}`}>
                    {dueFmt.text}
                  </p>
                )}
              </div>
            </div>
            <div className="space-y-1.5">
              {hw.problems.map((prob) => {
                const isSubmitted = prob.submitted
                return (
                  <button
                    key={prob.problem_id}
                    disabled={isSubmitted}
                    className={`w-full text-left rounded-lg border px-3 py-2 text-sm transition-colors ${
                      isSubmitted
                        ? "opacity-50 cursor-not-allowed bg-muted/30"
                        : "bg-white hover:bg-gray-50 cursor-pointer shadow-sm dark:bg-card"
                    }`}
                    onClick={async () => {
                      if (isSubmitted) return
                      setHomeworkLoading(true)
                      try {
                        const p = await getProblem(prob.problem_id)
                        onSelectProblem(p)
                      } catch {
                        // ignore
                      } finally {
                        setHomeworkLoading(false)
                      }
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate">{prob.problem_title}</span>
                      {isSubmitted && (
                        <Badge variant="secondary" className="text-xs shrink-0">제출 완료</Badge>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
