import * as React from "react"
import { getTeacherProblems, deleteProblem, type TeacherProblemItem } from "@/api/problems"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import ProblemFormDialog from "./ProblemFormDialog"
import { Plus, Pencil, Trash2, ChevronLeft, ChevronRight } from "lucide-react"

const PAGE_SIZE = 50

export default function ProblemManager() {
  const [problems, setProblems] = React.useState<TeacherProblemItem[]>([])
  const [total, setTotal] = React.useState(0)
  const [page, setPage] = React.useState(1)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState("")
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [editTarget, setEditTarget] = React.useState<TeacherProblemItem | null>(null)

  async function load(p = page) {
    setLoading(true)
    setError("")
    try {
      const data = await getTeacherProblems({ page: p, page_size: PAGE_SIZE })
      setProblems(data.problems)
      setTotal(data.total)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "불러오기 실패")
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => { load(page) }, [page])  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleDelete(problem: TeacherProblemItem) {
    const msg = problem.submission_count > 0
      ? `"${problem.title}" 문제에 제출이 ${problem.submission_count}건 있습니다. 소프트 삭제됩니다. 계속하시겠습니까?`
      : `"${problem.title}" 문제를 삭제하시겠습니까?`
    if (!window.confirm(msg)) return
    try {
      await deleteProblem(problem.id)
      load(page)
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "삭제 실패")
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex justify-between items-center">
        <h2 className="text-base font-semibold">문제 목록 (총 {total}개)</h2>
        <Button size="sm" onClick={() => { setEditTarget(null); setDialogOpen(true) }}>
          <Plus className="h-4 w-4 mr-1" /> 문제 등록
        </Button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : (
        <div className="rounded-2xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="text-left px-4 py-3 font-medium">제목</th>
                <th className="text-left px-4 py-3 font-medium">도메인</th>
                <th className="text-left px-4 py-3 font-medium">난이도</th>
                <th className="text-right px-4 py-3 font-medium">제출수</th>
                <th className="text-right px-4 py-3 font-medium">생성일</th>
                <th className="text-right px-4 py-3 font-medium">액션</th>
              </tr>
            </thead>
            <tbody>
              {problems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-muted-foreground">
                    등록된 문제가 없습니다
                  </td>
                </tr>
              ) : (
                problems.map((p) => (
                  <tr key={p.id} className="border-t hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium">{p.title}</td>
                    <td className="px-4 py-3">
                      <Badge variant="secondary" className="max-w-[160px] truncate">{p.domain}</Badge>
                    </td>
                    <td className="px-4 py-3 text-amber-500">{"★".repeat(p.difficulty)}</td>
                    <td className="px-4 py-3 text-right">{p.submission_count}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">
                      {new Date(p.created_at).toLocaleDateString("ko-KR")}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => { setEditTarget(p); setDialogOpen(true) }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(p)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="icon" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">{page} / {totalPages}</span>
          <Button variant="outline" size="icon" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      <ProblemFormDialog
        open={dialogOpen}
        mode={editTarget ? "edit" : "create"}
        initial={editTarget}
        onClose={() => setDialogOpen(false)}
        onSaved={() => load(page)}
      />
    </div>
  )
}
