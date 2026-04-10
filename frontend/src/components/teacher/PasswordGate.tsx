import * as React from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface PasswordGateProps {
  onSuccess: () => void
}

export default function PasswordGate({ onSuccess }: PasswordGateProps) {
  const [password, setPassword] = React.useState("")
  const [error, setError] = React.useState("")
  const [loading, setLoading] = React.useState(false)

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      const res = await fetch("/api/v1/teacher/queue", {
        headers: { "X-Teacher-Password": password },
      })
      if (res.status === 401) {
        setError("비밀번호가 올바르지 않습니다")
        return
      }
      localStorage.setItem("argus_teacher_pw", password)
      onSuccess()
    } catch {
      setError("서버 연결에 실패했습니다")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center">Argus 교사 대시보드</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <Input
              type="password"
              placeholder="교사 비밀번호"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
            />
            {error && <p className="text-sm text-rose-500">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "확인 중..." : "로그인"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
