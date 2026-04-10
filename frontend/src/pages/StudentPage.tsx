import * as React from "react"
import {
  getSubmissionStatus,
  submitAnswerImage,
  submitAnswerText,
  type Problem,
  type SubmissionStatusResponse,
} from "@/api/submissions"
import StudentInfoForm from "@/components/student/StudentInfoForm"
import ProblemSelector from "@/components/student/ProblemSelector"
import AnswerInput from "@/components/student/AnswerInput"
import GradingStatus from "@/components/student/GradingStatus"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

type Stage = "info" | "problem" | "answer" | "submitting" | "polling" | "done"

export default function StudentPage() {
  const [stage, setStage] = React.useState<Stage>(() => {
    const saved = sessionStorage.getItem("argus_student_name")
    return saved ? "problem" : "info"
  })
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

  function reset() {
    setProblem(null)
    setTextAnswer("")
    setImageFile(null)
    setResult(null)
    setSubmissionId(null)
    setSubmitError("")
    setStage("problem")
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b sticky top-0 bg-background/80 backdrop-blur z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold text-primary">Argus</h1>
          {studentName && (
            <span className="text-sm text-muted-foreground">{studentName}</span>
          )}
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {stage === "info" && (
          <StudentInfoForm
            onComplete={(name, id) => {
              setStudentName(name)
              setStudentId(id)
              setStage("problem")
            }}
          />
        )}

        {stage === "problem" && (
          <Card>
            <CardHeader>
              <CardTitle>문제 선택</CardTitle>
            </CardHeader>
            <CardContent>
              <ProblemSelector
                onSelect={(p) => {
                  setProblem(p)
                  setStage("answer")
                }}
              />
            </CardContent>
          </Card>
        )}

        {stage === "answer" && problem && (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{problem.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap">{problem.content}</p>
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
        )}

        {stage === "submitting" && (
          <Card>
            <CardContent className="p-8 text-center space-y-3">
              <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-sm text-muted-foreground">제출 중입니다...</p>
            </CardContent>
          </Card>
        )}

        {stage === "polling" && (
          <Card>
            <CardContent className="p-8 text-center space-y-3">
              <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-sm text-muted-foreground">채점 중입니다. 잠시만 기다려주세요...</p>
            </CardContent>
          </Card>
        )}

        {stage === "done" && result && (
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
        )}
      </main>
    </div>
  )
}
