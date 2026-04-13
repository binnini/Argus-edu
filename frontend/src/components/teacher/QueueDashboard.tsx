import { useCallback, useEffect, useMemo, useState } from "react"
import { getQueueHealth } from "@/api/teacher"
import { MetricCard } from "@/components/ui/metric-card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

type QueueStats = Record<string, number>

function queueValue(stats: QueueStats | undefined, key: string): number {
  return Number(stats?.[key] ?? 0)
}

export default function QueueDashboard() {
  const [queues, setQueues] = useState<Record<string, QueueStats>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const data = await getQueueHealth()
      setQueues(data.queues ?? {})
    } catch (e) {
      setError(e instanceof Error ? e.message : "작업 큐 조회 실패")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const id = window.setInterval(() => {
      void load()
    }, 3000)
    return () => window.clearInterval(id)
  }, [load])

  const feedback = useMemo(() => queues.feedback ?? {}, [queues.feedback])
  const hallucination = useMemo(() => queues.hallucination ?? {}, [queues.hallucination])

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">작업 큐 현황</h2>
        <Button variant="outline" size="sm" onClick={() => void load()}>
          새로고침
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">Feedback Queue</p>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard value={queueValue(feedback, "pending")} label="대기" />
          <MetricCard value={queueValue(feedback, "running")} label="실행 중" />
          <MetricCard value={queueValue(feedback, "done")} label="완료" />
          <MetricCard value={queueValue(feedback, "failed")} label="실패" valueClassName="text-red-600" />
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">Hallucination Queue</p>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard value={queueValue(hallucination, "pending")} label="대기" />
          <MetricCard value={queueValue(hallucination, "running")} label="실행 중" />
          <MetricCard value={queueValue(hallucination, "done")} label="완료" />
          <MetricCard value={queueValue(hallucination, "failed")} label="실패" valueClassName="text-red-600" />
        </div>
      </div>
    </div>
  )
}
