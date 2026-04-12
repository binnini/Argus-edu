import * as React from "react"
import { getTeacherProblems, deleteProblem, type TeacherProblemItem } from "@/api/problems"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import ProblemFormDialog from "./ProblemFormDialog"
import { Plus, Pencil, Trash2, ChevronLeft, ChevronRight, Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

function getSchoolLevel(domain: string): "초등" | "중등" | "고등" | "기타" {
  if (!domain) return "기타"
  if (domain.includes("초등") || /^[1-6]학년/.test(domain)) return "초등"
  if (domain.includes("중") || /중[1-3]/.test(domain)) return "중등"
  if (domain.includes("고") || domain.includes("수학") || /수[12]/.test(domain)) return "고등"
  return "기타"
}

const LEVEL_COLORS: Record<string, string> = {
  "초등": "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400",
  "중등": "bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400",
  "고등": "bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:text-purple-400",
  "기타": "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
}

const PAGE_SIZE = 50

export default function ProblemManager() {
  const [problems, setProblems] = React.useState<TeacherProblemItem[]>([])
  const [total, setTotal] = React.useState(0)
  const [page, setPage] = React.useState(1)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState("")
  const [dialogOpen, setDialogOpen] = React.useState(false)
  const [editTarget, setEditTarget] = React.useState<TeacherProblemItem | null>(null)
  const [searchText, setSearchText] = React.useState("")
  const [levelFilter, setLevelFilter] = React.useState("전체")
  const [domainFilter, setDomainFilter] = React.useState("전체")
  const [difficultyFilter, setDifficultyFilter] = React.useState("전체")
  const [sortBy, setSortBy] = React.useState("최신순")

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

  const domains = React.useMemo(
    () => ["전체", ...Array.from(new Set(problems.map(p => p.domain))).filter(Boolean).sort()],
    [problems]
  )

  const filteredProblems = React.useMemo(() => {
    let list = [...problems]
    if (searchText.trim()) {
      const q = searchText.toLowerCase()
      list = list.filter(p => p.title.toLowerCase().includes(q) || p.domain.toLowerCase().includes(q))
    }
    if (levelFilter !== "전체") list = list.filter(p => getSchoolLevel(p.domain) === levelFilter)
    if (domainFilter !== "전체") list = list.filter(p => p.domain === domainFilter)
    if (difficultyFilter !== "전체") list = list.filter(p => p.difficulty === Number(difficultyFilter))
    switch (sortBy) {
      case "최신순": list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()); break
      case "제목순": list.sort((a, b) => a.title.localeCompare(b.title, "ko")); break
      case "제출수": list.sort((a, b) => b.submission_count - a.submission_count); break
      case "난이도↑": list.sort((a, b) => a.difficulty - b.difficulty); break
      case "난이도↓": list.sort((a, b) => b.difficulty - a.difficulty); break
    }
    return list
  }, [problems, searchText, levelFilter, domainFilter, difficultyFilter, sortBy])

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex justify-between items-center">
        <h2 className="text-base font-semibold text-gray-900 dark:text-gray-50">문제 목록 (총 {total}개)</h2>
        <Button size="sm" onClick={() => { setEditTarget(null); setDialogOpen(true) }}>
          <Plus className="h-4 w-4 mr-1" /> 문제 등록
        </Button>
      </div>

      {/* FilterBar */}
      <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-3 shadow-sm dark:bg-card">
        <div className="flex gap-2 items-center flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="제목 또는 도메인 검색..."
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {["최신순", "제목순", "제출수", "난이도↑", "난이도↓"].map(s => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex gap-1.5 flex-wrap items-center">
          <span className="text-xs text-muted-foreground">학교급:</span>
          {["전체", "초등", "중등", "고등", "기타"].map(level => (
            <button
              key={level}
              onClick={() => setLevelFilter(level)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                levelFilter === level ? "bg-primary text-primary-foreground border-primary" : "border-border hover:bg-accent"
              }`}
            >
              {level}
            </button>
          ))}
          <span className="text-xs text-muted-foreground mx-1">|</span>
          <Select value={domainFilter} onValueChange={setDomainFilter}>
            <SelectTrigger className="h-7 text-xs w-40">
              <SelectValue placeholder="도메인 전체" />
            </SelectTrigger>
            <SelectContent>
              {domains.map(d => <SelectItem key={d} value={d} className="text-xs">{d}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={difficultyFilter} onValueChange={setDifficultyFilter}>
            <SelectTrigger className="h-7 text-xs w-28">
              <SelectValue placeholder="난이도 전체" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="전체" className="text-xs">난이도 전체</SelectItem>
              {[1,2,3,4,5].map(d => (
                <SelectItem key={d} value={String(d)} className="text-xs">{"★".repeat(d)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {(searchText || levelFilter !== "전체" || domainFilter !== "전체" || difficultyFilter !== "전체") && (
            <span className="text-xs text-muted-foreground ml-1">{filteredProblems.length}건</span>
          )}
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm dark:bg-card">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-muted">
              <tr>
                <th className="text-left px-4 py-3 font-semibold text-gray-900 dark:text-gray-50">제목</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-900 dark:text-gray-50">학교급</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-900 dark:text-gray-50">도메인</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-900 dark:text-gray-50">난이도</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-900 dark:text-gray-50">제출수</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-900 dark:text-gray-50">생성일</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-900 dark:text-gray-50">액션</th>
              </tr>
            </thead>
            <tbody>
              {filteredProblems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-muted-foreground">
                    등록된 문제가 없습니다
                  </td>
                </tr>
              ) : (
                filteredProblems.map((p) => (
                  <tr key={p.id} className="border-t hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium">{p.title}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${LEVEL_COLORS[getSchoolLevel(p.domain)]}`}>
                        {getSchoolLevel(p.domain)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="secondary" className="max-w-[140px] truncate text-xs">{p.domain}</Badge>
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
