import * as React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { verifyStudent } from "@/api/submissions"

interface StudentInfoFormProps {
  onComplete: (name: string, id: string) => void
}

export default function StudentInfoForm({ onComplete }: StudentInfoFormProps) {
  const [name, setName] = React.useState("")
  const [id, setId] = React.useState("")
  const [error, setError] = React.useState("")
  const [loading, setLoading] = React.useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      setError("이름을 입력해주세요")
      return
    }
    if (!id.trim()) {
      setError("학번을 입력해주세요")
      return
    }

    setLoading(true)
    setError("")
    try {
      const result = await verifyStudent(id.trim(), name.trim())
      if (!result.valid) {
        setError(result.message || "이름과 학번이 일치하지 않습니다.")
        return
      }
      sessionStorage.setItem("argus_student_name", name.trim())
      sessionStorage.setItem("argus_student_id", id.trim())
      onComplete(name.trim(), id.trim())
    } catch {
      // 서버 오류 시 허용 (네트워크 문제 등)
      sessionStorage.setItem("argus_student_name", name.trim())
      sessionStorage.setItem("argus_student_id", id.trim())
      onComplete(name.trim(), id.trim())
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle>학생 정보 입력</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium">이름 <span className="text-destructive">*</span></label>
            <Input
              placeholder="홍길동"
              value={name}
              onChange={(e) => { setName(e.target.value); setError("") }}
              disabled={loading}
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">학번 <span className="text-destructive">*</span></label>
            <Input
              placeholder="20240001"
              value={id}
              onChange={(e) => { setId(e.target.value); setError("") }}
              disabled={loading}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "확인 중..." : "계속하기"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
