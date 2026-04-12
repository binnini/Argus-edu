import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex min-h-56 flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 bg-white p-10 text-center shadow-sm dark:border-zinc-800 dark:bg-card",
        className
      )}
    >
      <Icon className="h-12 w-12 text-gray-300 dark:text-zinc-600" />
      <p className="mt-3 text-sm font-semibold text-gray-900 dark:text-gray-50">{title}</p>
      {description && <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
