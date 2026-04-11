import { useState, useEffect, useCallback } from "react"
import { getSubmissions } from "@/api/teacher"
import type { SubmissionOverviewItem } from "@/api/teacher"
import { getTeacherProblems } from "@/api/problems"
import type { TeacherProblemItem } from "@/api/problems"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import SubmissionDetailDialog from "./SubmissionDetailDialog"
import { Search, ChevronLeft, ChevronRight } from "lucide-react"

function statusBadge(status: string) {
  switch (status) {
    case "pending": return <Badge variant="secondary">채점 중</Badge>
    case "graded": return <Badge variant="warning">검토 대기</Badge>
    case "approved": return <Badge variant="success">승인</Badge>
    case "rejected": return <Badge variant="destructive">거부</Badge>
    default: return <Badge variant="secondary">{status}</Badge>
  }
}

function inputTypeIcon(type: string) {
  switch (type) {
    case "image": return "📷"
    case "canvas": return "✏️"
    default: return "📝"
  }
}

export default function SubmissionOverview() {
  const [items, setItems] = useState<SubmissionOverviewItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [problems, setProblems] = useState<TeacherProblemItem[]>([])
  const [filterProblem, setFilterProblem] = useState<string>("")
  const [filterStatus, setFilterStatus] = useState<string>("")
  const [filterName, setFilterName] = useState("")
  const [nameInput, setNameInput] = useState("")

  const [selected, setSelected] = useState<SubmissionOverviewItem | null>(null)

  const PAGE_SIZE = 20

  useEffect(() => {
    getTeacherProblems({ has_submissions: true, page_size: 200 })
      .then((data) => setProblems(data.problems))
      .catch(() => {/* 문제 목록 조회 실패 시 필터 없이 진행 */})
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getSubmissions({
        problem_id: filterProblem ? Number(filterProblem) : undefined,
        status: filterStatus || undefined,
        student_name: filterName || undefined,
        page,
        page_size: PAGE_SIZE,
      })
      setItems(data.submissions)
      setTotal(data.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : "조회 실패")
    } finally {
      setLoading(false)
    }
  }, [filterProblem, filterStatus, filterName, page])

  useEffect(() => { load() }, [load])

  function handleSearch() {
    setFilterName(nameInput)
    setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-4">
      {/* 필터 바 */}
      <div className="flex flex-wrap gap-2 items-end">
        <Select value={filterProblem} onValueChange={(v) => { setFilterProblem(v === "all" ? "" : v); setPage(1) }}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="문제 전체" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">문제 전체</SelectItem>
            {problems.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>{p.title}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={filterStatus} onValueChange={(v) => { setFilterStatus(v === "all" ? "" : v); setPage(1) }}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="상태 전체" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">상태 전체</SelectItem>
            <SelectItem value="pending">채점 중</SelectItem>
            <SelectItem value="graded">검토 대기</SelectItem>
            <SelectItem value="approved">승인</SelectItem>
            <SelectItem value="rejected">거부</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex gap-1">
          <Input
            placeholder="학생 이름 검색"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-40"
          />
          <Button variant="outline" size="icon" onClick={handleSearch}>
            <Search className="h-4 w-4" />
          </Button>
        </div>

        <span className="text-xs text-muted-foreground ml-auto">총 {total}건</span>
      </div>

      {/* 테이블 */}
      {loading ? (
        <div className="space-y-2">
          {[1,2,3,4,5].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-6 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={load} className="mt-3">다시 시도</Button>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border bg-card p-12 text-center">
          <p className="text-muted-foreground text-sm">제출 내역이 없습니다</p>
        </div>
      ) : (
        <div className="rounded-2xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">학생</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">문제</th>
                <th className="text-center px-3 py-3 font-medium text-muted-foreground">입력</th>
                <th className="text-center px-3 py-3 font-medium text-muted-foreground">상태</th>
                <th className="text-center px-3 py-3 font-medium text-muted-foreground">결과</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">제출시각</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.submission_id}
                  className="border-t hover:bg-muted/30 cursor-pointer transition-colors"
                  onClick={() => setSelected(item)}
                >
                  <td className="px-4 py-3">
                    <span className="font-medium">{item.student_name}</span>
                    {item.student_id && (
                      <span className="text-xs text-muted-foreground ml-1">({item.student_id})</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground max-w-[200px] truncate">{item.problem_title}</td>
                  <td className="px-3 py-3 text-center text-base">{inputTypeIcon(item.input_type)}</td>
                  <td className="px-3 py-3 text-center">{statusBadge(item.status)}</td>
                  <td className="px-3 py-3 text-center font-medium">
                    {item.final_score === null ? "—" : item.final_score > 0 ? (
                      <Badge variant="success">정답</Badge>
                    ) : (
                      <Badge variant="destructive">오답</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(item.submitted_at).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 페이지네이션 */}
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

      <SubmissionDetailDialog item={selected} open={!!selected} onClose={() => setSelected(null)} />
    </div>
  )
}
