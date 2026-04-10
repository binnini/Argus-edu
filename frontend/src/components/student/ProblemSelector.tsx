import * as React from "react"
import { getProblems, type Problem } from "@/api/submissions"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent } from "@/components/ui/card"

interface ProblemSelectorProps {
  onSelect: (problem: Problem) => void
}

export default function ProblemSelector({ onSelect }: ProblemSelectorProps) {
  const [problems, setProblems] = React.useState<Problem[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState("")

  React.useEffect(() => {
    getProblems()
      .then(setProblems)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "불러오기 실패"))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-3/4" />
      </div>
    )
  }

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }

  return (
    <div className="space-y-4">
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
              {p.title} ({p.domain} / 난이도 {p.difficulty})
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {problems.length === 0 && (
        <Card>
          <CardContent className="p-4 text-sm text-muted-foreground">
            등록된 문제가 없습니다.
          </CardContent>
        </Card>
      )}
    </div>
  )
}
