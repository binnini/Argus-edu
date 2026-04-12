import { useState, useEffect } from "react"
import {
  getGroups,
  getHomeworks,
  createHomework,
  deleteHomework,
  type GroupResponse,
  type HomeworkResponse,
} from "@/api/teacher"
import { getProblems, type Problem } from "@/api/submissions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ClipboardList, FileText } from "lucide-react"

export default function HomeworkManager() {
  const [homeworks, setHomeworks] = useState<HomeworkResponse[]>([])
  const [groups, setGroups] = useState<GroupResponse[]>([])
  const [problems, setProblems] = useState<Problem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 새 숙제 폼
  const [title, setTitle] = useState("")
  const [selectedGroupId, setSelectedGroupId] = useState<string>("")
  const [dueDate, setDueDate] = useState("")
  const [selectedProblemIds, setSelectedProblemIds] = useState<Set<number>>(new Set())
  const [creating, setCreating] = useState(false)

  async function fetchAll() {
    setLoading(true)
    setError(null)
    try {
      const [hwData, groupData, problemData] = await Promise.all([
        getHomeworks(),
        getGroups(),
        getProblems(1, 100),
      ])
      setHomeworks(hwData.homeworks)
      setGroups(groupData.groups)
      setProblems(problemData.problems)
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터 조회 실패")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
  }, [])

  function toggleProblem(problemId: number) {
    setSelectedProblemIds((prev) => {
      const next = new Set(prev)
      if (next.has(problemId)) {
        next.delete(problemId)
      } else {
        next.add(problemId)
      }
      return next
    })
  }

  async function handleCreateHomework() {
    if (!title.trim() || selectedProblemIds.size === 0) return
    setCreating(true)
    try {
      await createHomework({
        title: title.trim(),
        group_id: selectedGroupId ? Number(selectedGroupId) : null,
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
        problem_ids: Array.from(selectedProblemIds),
      })
      setTitle("")
      setSelectedGroupId("")
      setDueDate("")
      setSelectedProblemIds(new Set())
      await fetchAll()
    } catch (e) {
      setError(e instanceof Error ? e.message : "숙제 생성 실패")
    } finally {
      setCreating(false)
    }
  }

  async function handleDeleteHomework(homeworkId: number) {
    if (!confirm("숙제를 삭제하시겠습니까?")) return
    try {
      await deleteHomework(homeworkId)
      await fetchAll()
    } catch (e) {
      setError(e instanceof Error ? e.message : "숙제 삭제 실패")
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return "없음"
    return new Date(dateStr).toLocaleString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-500">{error}</p>}

      {/* 숙제 생성 폼 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">새 숙제 만들기</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm font-medium">숙제 제목</label>
            <Input
              placeholder="숙제 제목 입력"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">그룹 선택 (선택사항)</label>
            <select
              className="w-full rounded-lg border border-input bg-white px-3 py-2 text-sm dark:bg-background"
              value={selectedGroupId}
              onChange={(e) => setSelectedGroupId(e.target.value)}
            >
              <option value="">그룹 없음</option>
              {groups.map((g) => (
                <option key={g.id} value={String(g.id)}>
                  {g.name} ({g.members.length}명)
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">마감일 (선택사항)</label>
            <Input
              type="datetime-local"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              문제 선택 ({selectedProblemIds.size}개 선택됨)
            </label>
            {loading ? (
              <p className="text-sm text-muted-foreground">문제 로딩 중...</p>
            ) : problems.length === 0 ? (
              <p className="text-sm text-muted-foreground">등록된 문제가 없습니다.</p>
            ) : (
              <div className="max-h-48 overflow-y-auto space-y-1 rounded-lg border border-gray-200 bg-gray-50 p-2">
                {problems.map((problem) => (
                  <label
                    key={problem.id}
                    className="flex items-center gap-2 rounded-lg bg-white px-2 py-1.5 cursor-pointer hover:bg-gray-50 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={selectedProblemIds.has(problem.id)}
                      onChange={() => toggleProblem(problem.id)}
                    />
                    <span className="font-medium text-gray-900">{problem.title}</span>
                    {problem.domain && (
                      <span className="text-xs text-muted-foreground">[{problem.domain}]</span>
                    )}
                    <span className="text-xs text-muted-foreground ml-auto">{problem.total_score}점</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <Button
            onClick={handleCreateHomework}
            disabled={creating || !title.trim() || selectedProblemIds.size === 0}
            className="w-full"
          >
            {creating ? "생성 중..." : "숙제 생성"}
          </Button>
        </CardContent>
      </Card>

      {/* 숙제 목록 */}
      <div className="space-y-3">
        <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
          숙제 목록 ({homeworks.length}개)
        </h3>
        {loading && <p className="text-sm text-muted-foreground">로딩 중...</p>}
        {!loading && homeworks.length === 0 && (
          <div className="flex min-h-48 flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 bg-white p-10 text-center shadow-sm">
            <ClipboardList className="h-12 w-12 text-gray-300" />
            <p className="mt-3 text-sm font-semibold text-gray-900">등록된 숙제가 없습니다</p>
            <p className="mt-1 text-xs text-gray-500">상단에서 문제를 선택해 새 숙제를 만들 수 있습니다.</p>
          </div>
        )}
        {homeworks.map((hw) => (
          <Card key={hw.id}>
            <CardHeader className="py-3 px-4 flex flex-row items-start justify-between space-y-0">
              <div className="space-y-1">
                <CardTitle className="text-sm font-semibold">{hw.title}</CardTitle>
                <div className="flex gap-3 text-xs text-muted-foreground">
                  <span>그룹: {hw.group_name ?? "없음"}</span>
                  <span>마감: {formatDate(hw.due_date)}</span>
                  <span>문제 수: {hw.problems.length}개</span>
                </div>
                {hw.problems.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {hw.problems.map((p) => (
                      <span
                        key={p.problem_id}
                        className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600"
                      >
                        <FileText className="mr-1 h-3 w-3 text-gray-400" />
                        {p.problem_title || `문제 #${p.problem_id}`}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleDeleteHomework(hw.id)}
              >
                삭제
              </Button>
            </CardHeader>
          </Card>
        ))}
      </div>
    </div>
  )
}
