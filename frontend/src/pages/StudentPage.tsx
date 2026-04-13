// Student submission page renderer.

import { apiOrigin } from "@/api/client"
import type { StudentHistoryItem, StudentHomeworkItem } from "@/api/submissions"
import AnswerInput from "@/components/student/AnswerInput"
import GradingStatus from "@/components/student/GradingStatus"
import HomeworkTab from "@/components/student/HomeworkTab"
import ProblemSelector from "@/components/student/ProblemSelector"
import StudentInfoForm from "@/components/student/StudentInfoForm"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useStudentSubmission } from "@/hooks/useStudentSubmission"
import { renderMath } from "@/lib/renderMath"
import { BookOpen, ChevronLeft, ClipboardList, FileText, FolderOpen, LogOut, Plus } from "lucide-react"

function statusBadge(status: string) {
  switch (status) {
    case "auto_approved": return <Badge variant="success">자동 승인</Badge>
    case "approved": return <Badge variant="success">승인</Badge>
    case "graded": return <Badge variant="warning">검토 대기</Badge>
    case "rejected": return <Badge variant="destructive">거부</Badge>
    default: return <Badge variant="secondary">채점 중</Badge>
  }
}

function stageLabel(item: StudentHistoryItem): string {
  if (item.feedback_status === "running" || item.feedback_status === "pending") {
    return "AI 피드백 생성 중"
  }
  if (item.hallucination_status === "running" || item.hallucination_status === "pending") {
    return "신뢰도 판정 중"
  }
  if (item.status === "auto_approved" || item.auto_approved) {
    return "자동 승인 완료"
  }
  if (item.status === "approved") {
    return "교사 승인 완료"
  }
  if (item.status === "graded") {
    return "검토 대기"
  }
  if (item.status === "rejected") {
    return "검토 반려"
  }
  return "채점 중"
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

interface SidebarProps {
  homework: StudentHomeworkItem[]
  history: StudentHistoryItem[]
  onHomeworkClick: () => void
  onNewProblem: () => void
  onHistoryClick: (item: StudentHistoryItem) => void
}

function Sidebar({
  homework,
  history,
  onHomeworkClick,
  onNewProblem,
  onHistoryClick,
}: SidebarProps) {
  return (
    <aside className="hidden md:flex flex-col w-72 lg:w-80 shrink-0 border-r border-gray-200 bg-white/80 dark:bg-background/80 min-h-[calc(100vh-57px)] p-4 gap-5">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <ClipboardList className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-50">숙제 현황</span>
        </div>
        {homework.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-5 text-center">
            <FolderOpen className="mx-auto h-9 w-9 text-gray-300" />
            <p className="mt-2 text-xs font-medium text-gray-600">할당된 숙제가 없습니다</p>
          </div>
        ) : (
          <div className="space-y-2">
            {homework.map((hw) => {
              const dueFmt = formatDueDate(hw.due_date)
              const isDone = hw.completed_problems >= hw.total_problems
              return (
                <button
                  key={hw.homework_id}
                  className="w-full text-left rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm shadow-sm hover:bg-gray-50 transition-colors cursor-pointer dark:bg-card"
                  onClick={onHomeworkClick}
                >
                  <div className="flex items-start justify-between gap-1">
                    <span className="font-medium truncate text-gray-900 dark:text-gray-50">{hw.title}</span>
                    <span className={`text-xs shrink-0 font-mono ${isDone ? "text-green-600" : "text-muted-foreground"}`}>
                      {hw.completed_problems}/{hw.total_problems}
                    </span>
                  </div>
                  {dueFmt && (
                    <span className={`text-xs mt-0.5 block ${dueFmt.overdue ? "text-destructive" : "text-muted-foreground"}`}>
                      {dueFmt.text}{dueFmt.overdue ? " (마감)" : ""}
                    </span>
                  )}
                  <progress
                    className="mt-1.5 h-1 w-full rounded-full"
                    max={hw.total_problems}
                    value={hw.completed_problems}
                  />
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="border-t" />

      <div className="flex-1 min-h-0">
        <div className="flex items-center gap-2 mb-3">
          <BookOpen className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-50">풀이 현황</span>
        </div>
        {history.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-5 text-center">
            <FileText className="mx-auto h-9 w-9 text-gray-300" />
            <p className="mt-2 text-xs font-medium text-gray-600">아직 제출한 풀이가 없습니다</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {history.slice(0, 5).map((item) => (
              <button
                key={item.submission_id}
                className="w-full text-left rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs shadow-sm hover:bg-gray-50 transition-colors cursor-pointer dark:bg-card"
                onClick={() => onHistoryClick(item)}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="truncate font-medium text-gray-900 dark:text-gray-50">{item.problem_title}</span>
                  {statusBadge(item.status)}
                </div>
                <p className="mt-0.5 text-[11px] text-muted-foreground">{stageLabel(item)}</p>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="border-t pt-3">
        <Button size="sm" className="w-full gap-2" onClick={onNewProblem}>
          <Plus className="h-4 w-4" />
          새 문제 풀기
        </Button>
      </div>
    </aside>
  )
}

export default function StudentPage() {
  const student = useStudentSubmission()

  function renderProblemStage() {
    return (
      <div className="space-y-4">
        {student.submitNotice && (
          <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
            {student.submitNotice}
          </div>
        )}
        <Card>
          <CardHeader>
            <CardTitle>문제 선택</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs value={student.problemTab} onValueChange={(v) => student.setProblemTab(v as "homework" | "all")}>
              <TabsList className="w-full mb-4">
                <TabsTrigger value="homework" className="flex-1">숙제</TabsTrigger>
                <TabsTrigger value="all" className="flex-1">전체 문제</TabsTrigger>
              </TabsList>
              <TabsContent value="homework">
                <HomeworkTab
                  homework={student.homework}
                  homeworkLoading={student.homeworkLoading}
                  setHomeworkLoading={student.setHomeworkLoading}
                  onSelectProblem={(p) => {
                    student.setFinalAnswer("")
                    student.setProblem(p)
                    student.setStage("answer")
                  }}
                />
              </TabsContent>
              <TabsContent value="all">
                <ProblemSelector
                  onSelect={(p) => {
                    student.setFinalAnswer("")
                    student.setProblem(p)
                    student.setStage("answer")
                  }}
                />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    )
  }

  function renderAnswerStage() {
    if (!student.problem) return null
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>{student.problem.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm leading-relaxed">{renderMath(student.problem.content)}</div>
            <p className="text-xs text-muted-foreground mt-2">
              {student.problem.domain} | 난이도 {student.problem.difficulty} | {student.problem.total_score}점
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>답안 입력</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                최종 답 <span className="text-xs text-muted-foreground">(복수 정답은 쉼표 , 로 구분)</span>
              </label>
              <Input
                placeholder="예) x = 3, y = 5 또는 12cm², ③번"
                value={student.finalAnswer}
                onChange={(e) => student.setFinalAnswer(e.target.value)}
              />
            </div>
            <Tabs defaultValue="text" onValueChange={(v) => student.setInputMode(v as "text" | "image")}>
              <TabsList className="w-full">
                <TabsTrigger value="text" className="flex-1">텍스트 입력</TabsTrigger>
                <TabsTrigger value="image" className="flex-1">이미지 입력</TabsTrigger>
              </TabsList>
              <TabsContent value="text">
                <Textarea
                  placeholder="풀이 과정을 입력하세요..."
                  rows={6}
                  value={student.textAnswer}
                  onChange={(e) => student.setTextAnswer(e.target.value)}
                />
              </TabsContent>
              <TabsContent value="image">
                <AnswerInput
                  problemId={student.problem.id}
                  schoolLevel={student.problem.school_level}
                  domain={student.problem.domain}
                  onFileReady={(f) => student.setImageFile(f)}
                  onAutoFillFinalAnswer={(value) => student.setFinalAnswer(value)}
                />
              </TabsContent>
            </Tabs>

            {student.submitError && <p className="text-sm text-destructive">{student.submitError}</p>}

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => student.setStage("problem")}>이전</Button>
              <Button onClick={student.handleSubmit} className="flex-1">제출</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  function renderLoading(text: string) {
    return (
      <Card>
        <CardContent className="p-8 text-center space-y-3">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm text-muted-foreground">{text}</p>
        </CardContent>
      </Card>
    )
  }

  function renderDoneStage() {
    if (!student.result) return null
    return (
      <Card>
        <CardHeader>
          <CardTitle>채점 결과</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <GradingStatus result={student.result} />
          <Button variant="outline" onClick={student.reset} className="w-full">
            다른 문제 풀기
          </Button>
        </CardContent>
      </Card>
    )
  }

  function renderDetailStage() {
    if (!student.selectedHistory) return null
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            student.setStage("problem")
            student.setSelectedHistory(null)
            student.setDetailResult(null)
          }}
          className="gap-1"
        >
          <ChevronLeft className="h-4 w-4" /> 목록으로
        </Button>

        {student.detailResult?.problem_content && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">
                {student.detailResult.problem_title ?? student.selectedHistory.problem_title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm leading-relaxed">{renderMath(student.detailResult.problem_content)}</div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">내 답변</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(student.selectedHistory.input_type === "image" || student.selectedHistory.input_type === "canvas") && student.selectedHistory.image_path ? (
              <>
                <img
                  src={`${apiOrigin()}/${student.selectedHistory.image_path}`}
                  alt="제출 이미지"
                  className="max-w-full max-h-[400px] rounded-lg border object-contain"
                />
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">OCR 결과</p>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm leading-relaxed whitespace-pre-wrap">
                    {student.detailResult?.ocr_raw_text
                      ? renderMath(student.detailResult.ocr_raw_text)
                      : "OCR 결과가 아직 없습니다."}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-sm leading-relaxed whitespace-pre-wrap">
                {student.selectedHistory.student_answer ?? "—"}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">채점 결과</CardTitle>
          </CardHeader>
          <CardContent>
            {student.detailResult ? (
              <GradingStatus result={student.detailResult} />
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

  function renderStage() {
    if (student.stage === "problem") return renderProblemStage()
    if (student.stage === "answer") return renderAnswerStage()
    if (student.stage === "submitting") return renderLoading("제출 중입니다...")
    if (student.stage === "polling") return renderLoading("채점 중입니다. 잠시만 기다려주세요...")
    if (student.stage === "done") return renderDoneStage()
    if (student.stage === "detail") return renderDetailStage()
    return null
  }

  if (student.stage === "info") {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-background">
        <header className="border-b border-gray-200 sticky top-0 bg-white/85 backdrop-blur z-10 dark:bg-background/80">
          <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
            <h1 className="text-lg font-bold text-primary">Argus</h1>
          </div>
        </header>
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StudentInfoForm
            onComplete={(name, id) => {
              student.setStudentName(name)
              student.setStudentId(id)
              student.loadSidebar(id)
              student.setStage("problem")
            }}
          />
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-background flex flex-col">
      <header className="border-b border-gray-200 sticky top-0 bg-white/85 backdrop-blur z-10 dark:bg-background/80">
        <div className="px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold text-primary">Argus</h1>
          <div className="flex items-center gap-3">
            {student.studentName && (
              <span className="text-sm text-muted-foreground">{student.studentName}</span>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={student.handleLogout}
              className="gap-1 text-muted-foreground hover:text-foreground"
            >
              <LogOut className="h-3.5 w-3.5" />
              로그아웃
            </Button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          homework={student.homework}
          history={student.history}
          onHistoryClick={student.loadDetail}
          onHomeworkClick={() => {
            student.setProblemTab("homework")
            student.setStage("problem")
          }}
          onNewProblem={() => {
            student.setProblemTab("all")
            student.setStage("problem")
          }}
        />

        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="max-w-2xl mx-auto px-4 py-6 space-y-4">
            {renderStage()}
          </div>
        </main>
      </div>
    </div>
  )
}
