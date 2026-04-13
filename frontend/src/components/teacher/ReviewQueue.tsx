import { useState, useEffect, useCallback, useMemo } from "react"
import { getQueue } from "@/api/teacher"
import type { QueueItem } from "@/api/teacher"
import ReviewCard from "./ReviewCard"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { MetricCard } from "@/components/ui/metric-card"
import { Skeleton } from "@/components/ui/skeleton"
import { ClipboardCheck, Search, ChevronLeft, ChevronRight } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

type TrustFilter = "all" | "high" | "low"
type ReviewStatusFilter = "pending" | "approved" | "modify" | "reject" | "reviewed" | "all"
const PAGE_SIZE = 20

export default function ReviewQueue() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<TrustFilter>("all")
  const [reviewStatus, setReviewStatus] = useState<ReviewStatusFilter>("pending")
  const [searchText, setSearchText] = useState("")
  const [sortBy, setSortBy] = useState<"sla" | "latest">("sla")
  const [problemFilter, setProblemFilter] = useState<string>("전체")

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const trustLevel = filter === "all" ? undefined : filter
      const data = await getQueue(trustLevel, reviewStatus, sortBy, page, PAGE_SIZE)
      setItems(data.queue)
      setTotal(data.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : "큐 조회 실패")
    } finally {
      setLoading(false)
    }
  }, [filter, reviewStatus, sortBy, page])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [filter, reviewStatus, sortBy])

  const problemTitles = useMemo(
    () => ["전체", ...Array.from(new Set(items.map(i => i.problem_title))).sort()],
    [items]
  )

  const filteredItems = useMemo(() => {
    let list = [...items]
    if (searchText.trim()) {
      const q = searchText.toLowerCase()
      list = list.filter(i =>
        i.student_name.toLowerCase().includes(q) ||
        i.problem_title.toLowerCase().includes(q)
      )
    }
    if (problemFilter !== "전체") list = list.filter(i => i.problem_title === problemFilter)
    return list
  }, [items, searchText, problemFilter])
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const lowCount = items.filter((i) => i.trust_level === "low").length
  const slaUrgent = items.filter((i) => {
    const diff = new Date(i.sla_deadline).getTime() - Date.now()
    return diff < 3_600_000 * 3
  }).length

  return (
    <div className="space-y-6">
      {/* 통계 카드 */}
      <div className="grid grid-cols-3 gap-3">
        <MetricCard value={total} label="미처리" />
        <MetricCard value={lowCount} label="신뢰도 Low" valueClassName="text-rose-600" />
        <MetricCard value={slaUrgent} label="SLA 3시간 내" valueClassName="text-amber-600" />
      </div>

      {/* 필터 */}
      <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-3 shadow-sm dark:bg-card">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-200">신뢰도 필터:</span>
        {(["all", "high", "low"] as TrustFilter[]).map((f) => (
          <Button
            key={f}
            variant={filter === f ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "전체" : f === "high" ? "High" : "Low"}
            {f !== "all" && (
              <Badge
                variant={f === "low" ? "destructive" : "success"}
                className="ml-1.5 text-xs px-1.5 py-0"
              >
                {f === "low" ? lowCount : items.length - lowCount}
              </Badge>
            )}
          </Button>
        ))}
        <Button variant="ghost" size="sm" onClick={load} className="ml-auto">
          새로고침
        </Button>
      </div>

      {/* 검색 + 정렬 */}
      <div className="flex flex-wrap gap-2 items-center rounded-lg border border-gray-200 bg-white p-3 shadow-sm dark:bg-card">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="학생명 또는 문제명 검색..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="pl-8"
          />
        </div>
        <Select value={problemFilter} onValueChange={setProblemFilter}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="문제 전체" />
          </SelectTrigger>
          <SelectContent>
            {problemTitles.map(t => (
              <SelectItem key={t} value={t} className="text-xs">{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={reviewStatus} onValueChange={(v) => setReviewStatus(v as ReviewStatusFilter)}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pending">미처리</SelectItem>
            <SelectItem value="approved">승인 완료</SelectItem>
            <SelectItem value="modify">수정 완료</SelectItem>
            <SelectItem value="reject">거부 완료</SelectItem>
            <SelectItem value="reviewed">처리 완료</SelectItem>
            <SelectItem value="all">전체</SelectItem>
          </SelectContent>
        </Select>
        <Select value={sortBy} onValueChange={(v) => setSortBy(v as "sla" | "latest")}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="sla">SLA 임박순</SelectItem>
            <SelectItem value="latest">최신순</SelectItem>
          </SelectContent>
        </Select>
        {(searchText || problemFilter !== "전체") && (
          <span className="text-xs text-muted-foreground">{filteredItems.length}/{items.length}건</span>
        )}
      </div>

      {/* 목록 */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-6 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" onClick={load} className="mt-3">
            다시 시도
          </Button>
        </div>
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title="검토할 항목이 없습니다"
          description="현재 승인이나 수정이 필요한 풀이가 없습니다."
          className="min-h-60"
        />
      ) : (
        <>
          <div className="space-y-4">
            {filteredItems.map((item) => (
              <ReviewCard key={item.queue_id} item={item} onActionComplete={load} />
            ))}
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-1">
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground w-20 text-center">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || loading}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
