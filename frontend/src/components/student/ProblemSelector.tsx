import * as React from "react"
import { getProblems, type Problem } from "@/api/submissions"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface ProblemSelectorProps {
  onSelect: (problem: Problem) => void
}

const PAGE_SIZE = 30

export default function ProblemSelector({ onSelect }: ProblemSelectorProps) {
  const [problems, setProblems] = React.useState<Problem[]>([])
  const [total, setTotal] = React.useState(0)
  const [page, setPage] = React.useState(1)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState("")

  React.useEffect(() => {
    setLoading(true)
    getProblems(page, PAGE_SIZE)
      .then((data) => {
        setProblems(data.problems)
        setTotal(data.total)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "불러오기 실패"))
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-8 w-1/2" />
      </div>
    )
  }

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }

  return (
    <div className="space-y-3">
      <Select onValueChange={(val) => {
        const p = problems.find((x) => x.id === Number(val))
        if (p) onSelect(p)
      }}>
        <SelectTrigger>
          <SelectValue placeholder="문제를 선택하세요" />
        </SelectTrigger>
        <SelectContent>
          {problems.map((p) => (
            <SelectItem key={p.id} value={String(p.id)}>
              {p.domain} — {p.title} (난이도 {p.difficulty})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>총 {total}개 문제 · {page}/{totalPages} 페이지</span>
          <div className="flex gap-1">
            <Button variant="outline" size="icon" className="h-7 w-7"
              onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
              <ChevronLeft className="h-3 w-3" />
            </Button>
            <Button variant="outline" size="icon" className="h-7 w-7"
              onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
              <ChevronRight className="h-3 w-3" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
