import * as React from "react"
import { Button } from "@/components/ui/button"
import { Moon, Sun } from "lucide-react"

interface DashboardHeaderProps {
  onLogout: () => void
}

export default function DashboardHeader({ onLogout }: DashboardHeaderProps) {
  const [dark, setDark] = React.useState(() => {
    return localStorage.getItem("argus_dark_mode") === "true"
  })

  React.useEffect(() => {
    if (dark) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
    localStorage.setItem("argus_dark_mode", String(dark))
  }, [dark])

  return (
    <header className="border-b border-gray-200 sticky top-0 z-10 bg-white/85 backdrop-blur dark:bg-background/80">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-primary">Argus</span>
          <span className="text-sm text-muted-foreground">교사 대시보드</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setDark(!dark)}
            aria-label="다크모드 토글"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="sm" onClick={onLogout}>
            로그아웃
          </Button>
        </div>
      </div>
    </header>
  )
}
