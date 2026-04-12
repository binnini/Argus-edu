import * as React from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import RubricEditor from "./RubricEditor"
import { createProblem, updateProblem, type ProblemCreate, type RubricSchema, type TeacherProblemItem } from "@/api/problems"

const DOMAINS = ["수학1", "수학2", "미적분", "확률과통계", "기하", "수학(하)", "수학(상)", "대수", "미적분I", "미적분II"]

const emptyRubric: RubricSchema = { total_score: 0, steps: [] }

interface ProblemFormDialogProps {
  open: boolean
  mode: "create" | "edit"
  initial?: TeacherProblemItem | null
  onClose: () => void
  onSaved: () => void
}

export default function ProblemFormDialog({
  open,
  mode,
  initial,
  onClose,
  onSaved,
}: ProblemFormDialogProps) {
  const [title, setTitle] = React.useState(initial?.title ?? "")
  const [content, setContent] = React.useState(initial?.content ?? "")
  const [answer, setAnswer] = React.useState(initial?.answer ?? "")
  const [refSolution, setRefSolution] = React.useState(initial?.reference_solution ?? "")
  const [rubric, setRubric] = React.useState<RubricSchema>(
    initial?.rubric ? (initial.rubric as unknown as RubricSchema) : emptyRubric
  )
  const [domain, setDomain] = React.useState(initial?.domain ?? "수학2")
  const [difficulty, setDifficulty] = React.useState(String(initial?.difficulty ?? "2"))
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState("")

  React.useEffect(() => {
    if (open) {
      setTitle(initial?.title ?? "")
      setContent(initial?.content ?? "")
      setAnswer(initial?.answer ?? "")
      setRefSolution(initial?.reference_solution ?? "")
      setRubric(initial?.rubric ? (initial.rubric as unknown as RubricSchema) : emptyRubric)
      setDomain(initial?.domain ?? "수학2")
      setDifficulty(String(initial?.difficulty ?? "2"))
      setError("")
    }
  }, [open, initial])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    if (!title.trim() || !content.trim() || !answer.trim() || !refSolution.trim()) {
      setError("모든 필수 항목을 입력해주세요")
      return
    }
    const payload: ProblemCreate = {
      title: title.trim(),
      content: content.trim(),
      answer: answer.trim(),
      reference_solution: refSolution.trim(),
      rubric,
      domain,
      difficulty: Number(difficulty),
    }
    setSaving(true)
    try {
      if (mode === "create") {
        await createProblem(payload)
      } else if (initial) {
        await updateProblem(initial.id, payload)
      }
      onSaved()
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "저장 실패")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "문제 등록" : "문제 수정"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSave} className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium">제목 *</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="문제 제목" />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">문제 본문 *</label>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="문제 내용"
              rows={4}
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">정답 *</label>
            <Input value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="정답" />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">참조 풀이 *</label>
            <Textarea
              value={refSolution}
              onChange={(e) => setRefSolution(e.target.value)}
              placeholder="참조 풀이 과정"
              rows={6}
            />
          </div>
          <RubricEditor value={rubric} onChange={setRubric} />
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm font-medium">도메인</label>
              <Select value={domain} onValueChange={setDomain}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {DOMAINS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">난이도</label>
              <Select value={difficulty} onValueChange={setDifficulty}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5].map((d) => (
                    <SelectItem key={d} value={String(d)}>{"★".repeat(d)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose} className="flex-1">취소</Button>
            <Button type="submit" disabled={saving} className="flex-1">
              {saving ? "저장 중..." : "저장"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
