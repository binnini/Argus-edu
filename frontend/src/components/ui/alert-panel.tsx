import type { HTMLAttributes } from "react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

type AlertTone = "error" | "success" | "info" | "warning" | "neutral"

const toneClasses: Record<AlertTone, string> = {
  error: "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-200",
  success: "border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950/30 dark:text-green-200",
  info: "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-200",
  warning: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200",
  neutral: "border-gray-200 bg-gray-50 text-gray-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-gray-200",
}

const headingClasses: Record<AlertTone, string> = {
  error: "text-red-700 dark:text-red-300",
  success: "text-green-700 dark:text-green-300",
  info: "text-blue-700 dark:text-blue-300",
  warning: "text-amber-700 dark:text-amber-300",
  neutral: "text-gray-700 dark:text-gray-200",
}

interface AlertPanelProps extends HTMLAttributes<HTMLDivElement> {
  tone?: AlertTone
  icon?: LucideIcon
  title?: string
}

export function AlertPanel({ tone = "neutral", icon: Icon, title, className, children, ...props }: AlertPanelProps) {
  return (
    <div className={cn("rounded-lg border p-4", toneClasses[tone], className)} {...props}>
      {title && (
        <div className="mb-2 flex items-center gap-1.5">
          {Icon && <Icon className="h-3.5 w-3.5" />}
          <h4 className={cn("text-sm font-semibold", headingClasses[tone])}>{title}</h4>
        </div>
      )}
      {children}
    </div>
  )
}
