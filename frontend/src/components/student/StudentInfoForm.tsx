import * as React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { loginStudent, signupStudent, verifyStudent } from "@/api/submissions"
import { saveStudentSession } from "@/lib/session"

interface StudentInfoFormProps {
  onComplete: (name: string, id: string) => void
}

export default function StudentInfoForm({ onComplete }: StudentInfoFormProps) {
  const [mode, setMode] = React.useState<"login" | "signup" | "guest">("login")
  const [name, setName] = React.useState("")
  const [id, setId] = React.useState("")
  const [password, setPassword] = React.useState("")
  const [error, setError] = React.useState("")
  const [loading, setLoading] = React.useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id.trim()) {
      setError("학번을 입력해주세요")
      return
    }
    if (mode !== "login" && !name.trim()) {
      setError("이름을 입력해주세요")
      return
    }
    if (mode !== "guest" && password.trim().length < 4) {
      setError("비밀번호는 4자 이상 입력해주세요")
      return
    }

    setLoading(true)
    setError("")
    try {
      if (mode === "signup") {
        const result = await signupStudent(id.trim(), name.trim(), password.trim())
        if (!result.valid) {
          setError(result.message || "회원가입에 실패했습니다.")
          return
        }
        saveStudentSession(name.trim(), id.trim())
        onComplete(name.trim(), id.trim())
        return
      }

      if (mode === "login") {
        const result = await loginStudent(id.trim(), password.trim())
        if (!result.valid || !result.student_name || !result.student_id) {
          setError(result.message || "로그인에 실패했습니다.")
          return
        }
        saveStudentSession(result.student_name, result.student_id)
        onComplete(result.student_name, result.student_id)
        return
      }

      const result = await verifyStudent(id.trim(), name.trim())
      if (!result.valid) {
        setError(result.message || "이름과 학번이 일치하지 않습니다.")
        return
      }
      saveStudentSession(name.trim(), id.trim())
      onComplete(name.trim(), id.trim())
    } catch {
      if (mode === "guest") {
        // 서버 오류 시 허용 (게스트 시작)
        saveStudentSession(name.trim(), id.trim())
        onComplete(name.trim(), id.trim())
      } else {
        setError("요청 처리 중 오류가 발생했습니다.")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle>학생 로그인</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex gap-2">
          <Button
            type="button"
            variant={mode === "login" ? "default" : "outline"}
            className="flex-1"
            onClick={() => { setMode("login"); setError("") }}
          >
            로그인
          </Button>
          <Button
            type="button"
            variant={mode === "signup" ? "default" : "outline"}
            className="flex-1"
            onClick={() => { setMode("signup"); setError("") }}
          >
            회원가입
          </Button>
          <Button
            type="button"
            variant={mode === "guest" ? "default" : "outline"}
            className="flex-1"
            onClick={() => { setMode("guest"); setError("") }}
          >
            게스트
          </Button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode !== "login" && (
            <div className="space-y-1">
              <label className="text-sm font-medium">이름 <span className="text-destructive">*</span></label>
              <Input
                placeholder="홍길동"
                value={name}
                onChange={(e) => { setName(e.target.value); setError("") }}
                disabled={loading}
              />
            </div>
          )}
          <div className="space-y-1">
            <label className="text-sm font-medium">학번 <span className="text-destructive">*</span></label>
            <Input
              placeholder="20240001"
              value={id}
              onChange={(e) => { setId(e.target.value); setError("") }}
              disabled={loading}
            />
          </div>
          {mode !== "guest" && (
            <div className="space-y-1">
              <label className="text-sm font-medium">비밀번호 <span className="text-destructive">*</span></label>
              <Input
                type="password"
                placeholder="비밀번호 4자 이상"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError("") }}
                disabled={loading}
              />
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "처리 중..." : mode === "signup" ? "회원가입 후 시작" : mode === "guest" ? "게스트로 시작" : "로그인"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
