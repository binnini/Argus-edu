import * as React from "react"
import { getProblems, type Problem } from "@/api/submissions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { ChevronLeft, ChevronRight, FileQuestion, Search, X } from "lucide-react"

interface ProblemSelectorProps {
  onSelect: (problem: Problem) => void
}

const PAGE_SIZE = 10
const SCHOOL_LEVELS = ["초등학교", "중학교", "고등학교"] as const

const DIFFICULTY_LABELS: Record<number, string> = {
  1: "1등급",
  2: "2등급",
  3: "3등급",
  4: "4등급",
  5: "5등급",
}

const DIFFICULTY_COLORS: Record<number, string> = {
  1: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  2: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  3: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  4: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  5: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
}

export default function ProblemSelector({ onSelect }: ProblemSelectorProps) {
  const [problems, setProblems] = React.useState<Problem[]>([])
  const [total, setTotal] = React.useState(0)
  const [page, setPage] = React.useState(1)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState("")

  // 필터 상태
  const [searchInput, setSearchInput] = React.useState("")
  const [activeQ, setActiveQ] = React.useState("")
  const [activeDifficulty, setActiveDifficulty] = React.useState<number | undefined>(undefined)
  const [activeSchoolLevel, setActiveSchoolLevel] = React.useState<string | undefined>(undefined)

  const fetchProblems = React.useCallback((p: number, q: string, diff?: number, level?: string) => {
    setLoading(true)
    setError("")
    getProblems(p, PAGE_SIZE, { q: q || undefined, difficulty: diff, school_level: level })
      .then((data) => {
        setProblems(data.problems)
        setTotal(data.total)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "불러오기 실패"))
      .finally(() => setLoading(false))
  }, [])

  React.useEffect(() => {
    fetchProblems(page, activeQ, activeDifficulty, activeSchoolLevel)
  }, [page, activeQ, activeDifficulty, activeSchoolLevel, fetchProblems])

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setPage(1)
    setActiveQ(searchInput.trim())
  }

  function handleClearSearch() {
    setSearchInput("")
    setActiveQ("")
    setPage(1)
  }

  function handleDifficultyToggle(diff: number) {
    setActiveDifficulty(prev => prev === diff ? undefined : diff)
    setPage(1)
  }

  function handleSchoolLevelToggle(level: string) {
    setActiveSchoolLevel(prev => prev === level ? undefined : level)
    setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const hasFilter = activeQ || activeDifficulty != null || activeSchoolLevel != null

  return (
    <div className="space-y-4">
      {/* 검색 + 난이도 필터 */}
      <div className="space-y-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
            <Input
              placeholder="문제 제목 또는 도메인 검색..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-8 pr-8"
            />
            {searchInput && (
              <button
                type="button"
                onClick={handleClearSearch}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <Button type="submit" size="sm">검색</Button>
        </form>

        {/* 난이도 필터 칩 */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-muted-foreground mr-1">학교급:</span>
          {SCHOOL_LEVELS.map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => handleSchoolLevelToggle(level)}
              className={`text-xs px-2.5 py-1 rounded-full border font-medium transition-colors ${
                activeSchoolLevel === level
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background hover:bg-muted text-muted-foreground"
              }`}
            >
              {level}
            </button>
          ))}
          <span className="text-xs text-muted-foreground mx-1">|</span>
          <span className="text-xs text-muted-foreground mr-1">난이도:</span>
          {[1, 2, 3, 4, 5].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => handleDifficultyToggle(d)}
              className={`text-xs px-2.5 py-1 rounded-full border font-medium transition-colors ${
                activeDifficulty === d
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background hover:bg-muted text-muted-foreground"
              }`}
            >
              {DIFFICULTY_LABELS[d]}
            </button>
          ))}
          {hasFilter && (
            <button
              type="button"
              onClick={() => { handleClearSearch(); setActiveDifficulty(undefined); setActiveSchoolLevel(undefined) }}
              className="text-xs px-2 py-1 text-muted-foreground hover:text-foreground flex items-center gap-0.5"
            >
              <X className="h-3 w-3" /> 필터 초기화
            </button>
          )}
        </div>
      </div>

      {/* 결과 요약 */}
      {!loading && (
        <p className="text-xs text-muted-foreground">
          {hasFilter ? `검색 결과 ${total}개` : `전체 ${total}개 문제`}
          {totalPages > 1 && ` · ${page}/${totalPages} 페이지`}
        </p>
      )}

      {/* 문제 목록 */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : problems.length === 0 ? (
        <div className="flex min-h-48 flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 bg-gray-50 px-6 py-10 text-center">
          <FileQuestion className="h-12 w-12 text-gray-300" />
          <p className="mt-3 text-sm font-semibold text-gray-900">
            {hasFilter ? "검색 조건에 맞는 문제가 없습니다." : "등록된 문제가 없습니다."}
          </p>
          {hasFilter && <p className="mt-1 text-xs text-gray-500">검색어나 난이도 필터를 조정해 보세요.</p>}
        </div>
      ) : (
        <div className="space-y-2">
          {problems.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => onSelect(p)}
              className="w-full text-left rounded-lg border border-gray-200 bg-white px-4 py-2.5 shadow-sm hover:bg-gray-50 hover:border-primary/40 transition-all group dark:bg-card"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-primary transition-colors dark:text-gray-50">
                    {p.title}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">{p.domain}</p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {p.school_level && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      {p.school_level}
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${DIFFICULTY_COLORS[p.difficulty] ?? "bg-muted text-muted-foreground"}`}>
                    {DIFFICULTY_LABELS[p.difficulty] ?? `난이도 ${p.difficulty}`}
                  </span>
                  <span className="text-xs text-muted-foreground">{p.total_score}점</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-1">
          <Button
            variant="outline" size="icon" className="h-8 w-8"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-xs text-muted-foreground w-16 text-center">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline" size="icon" className="h-8 w-8"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || loading}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}
