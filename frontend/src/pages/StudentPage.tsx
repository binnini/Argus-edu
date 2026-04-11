import * as React from "react"
import {
  getSubmissionStatus,
  getStudentHistory,
  getStudentHomework,
  getProblem,
  submitAnswerImage,
  submitAnswerText,
  updateSubmission,
  type Problem,
  type SubmissionStatusResponse,
  type StudentHistoryItem,
  type StudentHomeworkItem,
} from "@/api/submissions"
import StudentInfoForm from "@/components/student/StudentInfoForm"
import ProblemSelector from "@/components/student/ProblemSelector"
import AnswerInput from "@/components/student/AnswerInput"
import GradingStatus from "@/components/student/GradingStatus"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { renderMath } from "@/lib/renderMath"
import { BookOpen, ChevronLeft, ClipboardList, Pencil, Plus } from "lucide-react"

type Stage = "info" | "problem" | "answer" | "submitting" | "polling" | "done" | "detail" | "editing"

function statusBadge(status: string) {
  switch (status) {
    case "approved": return <Badge variant="success">승인</Badge>
    case "graded": return <Badge variant="warning">검토 대기</Badge>
    case "rejected": return <Badge variant="destructive">거부</Badge>
    default: return <Badge variant="secondary">채점 중</Badge>
  }
}

function formatDueDate(due: string | null): { text: string; overdue: boolean } | null {
  if (!due) return null
  const d = new Date(due)
  const now = new Date()
  const overdue = d < now
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  const dd = String(d.getDate()).padStart(2, "0")
  return { text: `${mm}/${dd} 마감`, overdue }
}

export default function StudentPage() {
  const [stage, setStage] = React.useState<Stage>(() => {
    const saved = sessionStorage.getItem("argus_student_name")
    return saved ? "problem" : "info"
  })
  const [history, setHistory] = React.useState<StudentHistoryItem[]>([])
  const [homework, setHomework] = React.useState<StudentHomeworkItem[]>([])
  const [studentName, setStudentName] = React.useState(
    () => sessionStorage.getItem("argus_student_name") ?? ""
  )
  const [studentId, setStudentId] = React.useState(
    () => sessionStorage.getItem("argus_student_id") ?? undefined
  )
  const [problem, setProblem] = React.useState<Problem | null>(null)
  const [textAnswer, setTextAnswer] = React.useState("")
  const [imageFile, setImageFile] = React.useState<File | null>(null)
  const [inputMode, setInputMode] = React.useState<"text" | "image">("text")
  const [submissionId, setSubmissionId] = React.useState<number | null>(null)
  const [result, setResult] = React.useState<SubmissionStatusResponse | null>(null)
  const [submitError, setSubmitError] = React.useState("")
  const [selectedHistory, setSelectedHistory] = React.useState<StudentHistoryItem | null>(null)
  const [detailResult, setDetailResult] = React.useState<SubmissionStatusResponse | null>(null)
  const [editAnswer, setEditAnswer] = React.useState("")
  const [editError, setEditError] = React.useState("")
  const [editSubmitting, setEditSubmitting] = React.useState(false)
  // 초기 탭: 숙제가 있으면 "homework", 없으면 "all"
  const [problemTab, setProblemTab] = React.useState<"homework" | "all">("homework")
  const [homeworkLoading, setHomeworkLoading] = React.useState(false)

  async function loadSidebar(id: string) {
    try {
      const [histRes, hwRes] = await Promise.allSettled([
        getStudentHistory(id),
        getStudentHomework(id),
      ])
      if (histRes.status === "fulfilled") setHistory(histRes.value.submissions)
      if (hwRes.status === "fulfilled") setHomework(hwRes.value.homeworks)
    } catch {
      // ignore
    }
  }

  // 마운트 시 사이드바 데이터 로드 (새로고침 대응)
  React.useEffect(() => {
    const id = sessionStorage.getItem("argus_student_id")
    if (id && stage !== "info") {
      loadSidebar(id)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // polling
  React.useEffect(() => {
    if (stage !== "polling" || submissionId === null) return
    const interval = setInterval(async () => {
      try {
        const status = await getSubmissionStatus(submissionId)
        if (status.status !== "pending") {
          setResult(status)
          setStage("done")
          clearInterval(interval)
        }
      } catch {
        // ignore transient errors
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [stage, submissionId])

  async function handleSubmit() {
    if (!problem) return
    setSubmitError("")
    setStage("submitting")
    try {
      let res
      if (inputMode === "text") {
        res = await submitAnswerText(problem.id, textAnswer, studentName, studentId)
      } else {
        if (!imageFile) {
          setSubmitError("이미지를 선택해주세요")
          setStage("answer")
          return
        }
        res = await submitAnswerImage(problem.id, imageFile, studentName, studentId)
      }
      setSubmissionId(res.submission_id)
      setStage("polling")
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : "제출 실패")
      setStage("answer")
    }
  }

  async function loadDetail(item: StudentHistoryItem) {
    setSelectedHistory(item)
    setStage("detail")
    setDetailResult(null)
    try {
      const res = await getSubmissionStatus(item.submission_id)
      setDetailResult(res)
    } catch {
      // 조회 실패 시 history 데이터로 fallback
    }
  }

  async function handleEditSubmit() {
    if (!selectedHistory || !editAnswer.trim()) return
    setEditError("")
    setEditSubmitting(true)
    try {
      await updateSubmission(selectedHistory.submission_id, editAnswer)
      setSubmissionId(selectedHistory.submission_id)
      setSelectedHistory(null)
      setDetailResult(null)
      setStage("polling")
    } catch (e) {
      setEditError(e instanceof Error ? e.message : "수정 실패")
    } finally {
      setEditSubmitting(false)
    }
  }

  function reset() {
    setProblem(null)
    setTextAnswer("")
    setImageFile(null)
    setResult(null)
    setSubmissionId(null)
    setSubmitError("")
    if (studentId) {
      loadSidebar(studentId)
    }
    setStage("problem")
  }

  // ===== 사이드바 컴포넌트 =====
  function Sidebar() {
    return (
      <aside className="hidden md:flex flex-col w-72 lg:w-80 shrink-0 border-r bg-muted/20 min-h-[calc(100vh-57px)] p-4 gap-5">
        {/* 숙제 현황 */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <ClipboardList className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">숙제 현황</span>
          </div>
          {homework.length === 0 ? (
            <p className="text-xs text-muted-foreground pl-1">할당된 숙제가 없습니다</p>
          ) : (
            <div className="space-y-2">
              {homework.map((hw) => {
                const dueFmt = formatDueDate(hw.due_date)
                const progress = `${hw.completed_problems}/${hw.total_problems}`
                const isDone = hw.completed_problems >= hw.total_problems
                return (
                  <button
                    key={hw.homework_id}
                    className="w-full text-left rounded-lg border bg-background px-3 py-2.5 text-sm hover:bg-muted/60 transition-colors cursor-pointer"
                    onClick={() => {
                      setProblemTab("homework")
                      setStage("problem")
                    }}
                  >
                    <div className="flex items-start justify-between gap-1">
                      <span className="font-medium truncate">{hw.title}</span>
                      <span className={`text-xs shrink-0 font-mono ${isDone ? "text-green-600" : "text-muted-foreground"}`}>
                        {progress}
                      </span>
                    </div>
                    {dueFmt && (
                      <span className={`text-xs mt-0.5 block ${dueFmt.overdue ? "text-destructive" : "text-muted-foreground"}`}>
                        {dueFmt.text}{dueFmt.overdue ? " (마감)" : ""}
                      </span>
                    )}
                    {/* 진행 바 */}
                    <div className="mt-1.5 h-1 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${isDone ? "bg-green-500" : "bg-primary"}`}
                        style={{ width: hw.total_problems > 0 ? `${(hw.completed_problems / hw.total_problems) * 100}%` : "0%" }}
                      />
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="border-t" />

        {/* 풀이 현황 */}
        <div className="flex-1 min-h-0">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">풀이 현황</span>
          </div>
          {history.length === 0 ? (
            <p className="text-xs text-muted-foreground pl-1">아직 제출한 풀이가 없습니다</p>
          ) : (
            <div className="space-y-1.5">
              {history.slice(0, 5).map((item) => (
                <button
                  key={item.submission_id}
                  className="w-full text-left rounded-lg border bg-background px-3 py-2 text-xs hover:bg-muted/60 transition-colors cursor-pointer"
                  onClick={() => loadDetail(item)}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="truncate font-medium">{item.problem_title}</span>
                    {statusBadge(item.status)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="border-t pt-3">
          <Button
            size="sm"
            className="w-full gap-2"
            onClick={() => {
              setProblemTab("all")
              setStage("problem")
            }}
          >
            <Plus className="h-4 w-4" />
            새 문제 풀기
          </Button>
        </div>
      </aside>
    )
  }

  // ===== 숙제 탭 콘텐츠 =====
  function HomeworkTab() {
    if (homeworkLoading) {
      return (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-6 justify-center">
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          불러오는 중...
        </div>
      )
    }
    if (homework.length === 0) {
      return (
        <div className="text-center py-8">
          <p className="text-sm text-muted-foreground">할당된 숙제가 없습니다</p>
          <p className="text-xs text-muted-foreground mt-1">선생님이 숙제를 할당할 때까지 기다려주세요</p>
        </div>
      )
    }
    return (
      <div className="space-y-6">
        {homework.map((hw) => {
          const dueFmt = formatDueDate(hw.due_date)
          return (
            <div key={hw.homework_id}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h3 className="text-sm font-semibold">{hw.title}</h3>
                  {hw.group_name && (
                    <span className="text-xs text-muted-foreground">{hw.group_name}</span>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-xs font-mono text-muted-foreground">
                    {hw.completed_problems}/{hw.total_problems}
                  </span>
                  {dueFmt && (
                    <p className={`text-xs ${dueFmt.overdue ? "text-destructive" : "text-muted-foreground"}`}>
                      {dueFmt.text}
                    </p>
                  )}
                </div>
              </div>
              <div className="space-y-1.5">
                {hw.problems.map((prob) => {
                  const isSubmitted = prob.submitted
                  return (
                    <button
                      key={prob.problem_id}
                      disabled={isSubmitted}
                      className={`w-full text-left rounded-lg border px-3 py-2.5 text-sm transition-colors ${
                        isSubmitted
                          ? "opacity-50 cursor-not-allowed bg-muted/30"
                          : "bg-background hover:bg-muted/50 cursor-pointer"
                      }`}
                      onClick={async () => {
                        if (isSubmitted) return
                        setHomeworkLoading(true)
                        try {
                          const p = await getProblem(prob.problem_id)
                          setProblem(p)
                          setStage("answer")
                        } catch {
                          // ignore
                        } finally {
                          setHomeworkLoading(false)
                        }
                      }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate">{prob.problem_title}</span>
                        {isSubmitted && (
                          <Badge variant="secondary" className="text-xs shrink-0">제출 완료</Badge>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // ===== stage별 메인 콘텐츠 =====
  function MainContent() {
    if (stage === "problem") {
      return (
        <Card>
          <CardHeader>
            <CardTitle>문제 선택</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={problemTab} onValueChange={(v) => setProblemTab(v as "homework" | "all")}>
              <TabsList className="w-full mb-4">
                <TabsTrigger value="homework" className="flex-1">숙제</TabsTrigger>
                <TabsTrigger value="all" className="flex-1">전체 문제</TabsTrigger>
              </TabsList>
              <TabsContent value="homework">
                <HomeworkTab />
              </TabsContent>
              <TabsContent value="all">
                <ProblemSelector
                  onSelect={(p) => {
                    setProblem(p)
                    setStage("answer")
                  }}
                />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )
    }

    if (stage === "answer" && problem) {
      return (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{problem.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm leading-relaxed">{renderMath(problem.content)}</div>
              <p className="text-xs text-muted-foreground mt-2">
                {problem.domain} | 난이도 {problem.difficulty} | {problem.total_score}점
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>답안 입력</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Tabs defaultValue="text" onValueChange={(v) => setInputMode(v as "text" | "image")}>
                <TabsList className="w-full">
                  <TabsTrigger value="text" className="flex-1">텍스트 입력</TabsTrigger>
                  <TabsTrigger value="image" className="flex-1">이미지 입력</TabsTrigger>
                </TabsList>
                <TabsContent value="text">
                  <Textarea
                    placeholder="풀이 과정을 입력하세요..."
                    rows={6}
                    value={textAnswer}
                    onChange={(e) => setTextAnswer(e.target.value)}
                  />
                </TabsContent>
                <TabsContent value="image">
                  <AnswerInput onFileReady={(f) => setImageFile(f)} />
                </TabsContent>
              </Tabs>

              {submitError && <p className="text-sm text-destructive">{submitError}</p>}

              <div className="flex gap-3">
                <Button variant="outline" onClick={() => setStage("problem")}>
                  이전
                </Button>
                <Button onClick={handleSubmit} className="flex-1">
                  제출
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    if (stage === "submitting") {
      return (
        <Card>
          <CardContent className="p-8 text-center space-y-3">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-muted-foreground">제출 중입니다...</p>
          </CardContent>
        </Card>
      )
    }

    if (stage === "polling") {
      return (
        <Card>
          <CardContent className="p-8 text-center space-y-3">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-sm text-muted-foreground">채점 중입니다. 잠시만 기다려주세요...</p>
          </CardContent>
        </Card>
      )
    }

    if (stage === "done" && result) {
      return (
        <Card>
          <CardHeader>
            <CardTitle>채점 결과</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <GradingStatus result={result} />
            <Button variant="outline" onClick={reset} className="w-full">
              다른 문제 풀기
            </Button>
          </CardContent>
        </Card>
      )
    }

    if (stage === "detail" && selectedHistory) {
      return (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setStage("problem"); setSelectedHistory(null); setDetailResult(null) }}
              className="gap-1"
            >
              <ChevronLeft className="h-4 w-4" /> 목록으로
            </Button>
          </div>

          {detailResult?.problem_content && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{detailResult.problem_title ?? selectedHistory.problem_title}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm leading-relaxed">{renderMath(detailResult.problem_content)}</div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">내 답변</CardTitle>
                {(selectedHistory.status === "pending" || selectedHistory.status === "graded") && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setEditAnswer(selectedHistory.student_answer ?? "")
                      setStage("editing")
                    }}
                    className="gap-1 text-xs"
                  >
                    <Pencil className="h-3 w-3" /> 수정하기
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {selectedHistory.input_type === "image" && selectedHistory.image_path ? (
                <img
                  src={`${(import.meta.env.VITE_API_BASE as string ?? "/api/v1").replace("/api/v1", "")}/${selectedHistory.image_path}`}
                  alt="제출 이미지"
                  className="max-w-full rounded-xl border"
                  style={{ maxHeight: "400px", objectFit: "contain" }}
                />
              ) : (
                <div className="text-sm leading-relaxed whitespace-pre-wrap">
                  {selectedHistory.student_answer ?? "—"}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">채점 결과</CardTitle>
            </CardHeader>
            <CardContent>
              {detailResult ? (
                <GradingStatus result={detailResult} />
              ) : (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  불러오는 중...
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )
    }

    if (stage === "editing" && selectedHistory) {
      return (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setStage("detail"); setEditError("") }}
              className="gap-1"
            >
              <ChevronLeft className="h-4 w-4" /> 상세로 돌아가기
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">답안 수정</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {selectedHistory.problem_title}
              </p>
              <Textarea
                placeholder="수정할 답안을 입력하세요..."
                rows={8}
                value={editAnswer}
                onChange={(e) => setEditAnswer(e.target.value)}
              />
              {editError && <p className="text-sm text-destructive">{editError}</p>}
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => { setStage("detail"); setEditError("") }}
                >
                  취소
                </Button>
                <Button
                  onClick={handleEditSubmit}
                  disabled={editSubmitting || !editAnswer.trim()}
                  className="flex-1"
                >
                  {editSubmitting ? "제출 중..." : "수정 제출"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return null
  }

  // ===== 전체 화면 렌더링 =====
  if (stage === "info") {
    return (
      <div className="min-h-screen bg-background">
        <header className="border-b sticky top-0 bg-background/80 backdrop-blur z-10">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
            <h1 className="text-lg font-bold text-primary">Argus</h1>
          </div>
        </header>
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StudentInfoForm
            onComplete={(name, id) => {
              setStudentName(name)
              setStudentId(id)
              if (id) {
                loadSidebar(id)
              }
              setStage("problem")
            }}
          />
        </main>
      </div>
    )
  }

  // 2단 레이아웃 (로그인 후)
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b sticky top-0 bg-background/80 backdrop-blur z-10">
        <div className="px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold text-primary">Argus</h1>
          {studentName && (
            <span className="text-sm text-muted-foreground">{studentName}</span>
          )}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
            <MainContent />
          </div>
        </main>
      </div>
    </div>
  )
}
