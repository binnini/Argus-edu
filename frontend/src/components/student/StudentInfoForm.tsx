import * as React from "react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface StudentInfoFormProps {
  onComplete: (name: string, id: string | undefined) => void
}

export default function StudentInfoForm({ onComplete }: StudentInfoFormProps) {
  const [name, setName] = React.useState("")
  const [id, setId] = React.useState("")
  const [error, setError] = React.useState("")

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      setError("이름을 입력해주세요")
      return
    }
    sessionStorage.setItem("argus_student_name", name.trim())
    if (id.trim()) {
      sessionStorage.setItem("argus_student_id", id.trim())
    } else {
      sessionStorage.removeItem("argus_student_id")
    }
    onComplete(name.trim(), id.trim() || undefined)
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
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium text-muted-foreground">학번 (선택)</label>
            <Input
              placeholder="20240001"
              value={id}
              onChange={(e) => setId(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full">계속하기</Button>
        </form>
      </CardContent>
    </Card>
  )
}
