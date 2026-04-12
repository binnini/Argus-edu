import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

interface MetricCardProps {
  value: ReactNode
  label: string
  className?: string
  valueClassName?: string
}

export function MetricCard({ value, label, className, valueClassName }: MetricCardProps) {
  return (
    <div className={cn("rounded-lg border border-gray-200 bg-white p-4 text-center shadow-sm dark:border-zinc-800 dark:bg-card", className)}>
      <p className={cn("text-2xl font-bold text-gray-900 dark:text-gray-50", valueClassName)}>{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  )
}
