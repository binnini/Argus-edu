// Student submission state and side effects.

import * as React from "react"

import {
  getSubmissionStatus,
  getStudentHistory,
  getStudentHomework,
  submitAnswerImage,
  submitAnswerText,
  type Problem,
  type SubmissionStatusResponse,
  type StudentHistoryItem,
  type StudentHomeworkItem,
} from "@/api/submissions"
import { clearStudentSession, getStudentSession, hasStudentSession } from "@/lib/session"

export type Stage = "info" | "problem" | "answer" | "submitting" | "polling" | "done" | "detail"

export function useStudentSubmission() {
  const savedSession = getStudentSession()
  const [stage, setStage] = React.useState<Stage>(() => hasStudentSession() ? "problem" : "info")
  const [history, setHistory] = React.useState<StudentHistoryItem[]>([])
  const [homework, setHomework] = React.useState<StudentHomeworkItem[]>([])
  const [studentName, setStudentName] = React.useState(savedSession.name)
  const [studentId, setStudentId] = React.useState(savedSession.id)
  const [finalAnswer, setFinalAnswer] = React.useState("")
  const [problem, setProblem] = React.useState<Problem | null>(null)
  const [textAnswer, setTextAnswer] = React.useState("")
  const [imageFile, setImageFile] = React.useState<File | null>(null)
  const [inputMode, setInputMode] = React.useState<"text" | "image">("text")
  const [submissionId, setSubmissionId] = React.useState<number | null>(null)
  const [result, setResult] = React.useState<SubmissionStatusResponse | null>(null)
  const [submitError, setSubmitError] = React.useState("")
  const [submitNotice, setSubmitNotice] = React.useState("")
  const [selectedHistory, setSelectedHistory] = React.useState<StudentHistoryItem | null>(null)
  const [detailResult, setDetailResult] = React.useState<SubmissionStatusResponse | null>(null)
  const [problemTab, setProblemTab] = React.useState<"homework" | "all">("homework")
  const [homeworkLoading, setHomeworkLoading] = React.useState(false)

  const loadSidebar = React.useCallback(async (id: string) => {
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
  }, [])

  React.useEffect(() => {
    const session = getStudentSession()
    if (session.id && stage !== "info") {
      loadSidebar(session.id)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    if (submissionId === null) return
    const interval = setInterval(async () => {
      try {
        const status = await getSubmissionStatus(submissionId)
        if (status.status !== "pending") {
          setResult(status)
          setSubmissionId(null)
          if (stage === "polling") {
            setStage("done")
          } else {
            setSubmitNotice("채점이 완료되었습니다. 풀이 현황에서 결과를 확인하세요.")
          }
          clearInterval(interval)
          const session = getStudentSession()
          if (session.id) loadSidebar(session.id)
        }
      } catch {
        // ignore transient errors
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [loadSidebar, stage, submissionId])

  async function handleSubmit() {
    if (!problem) return
    setSubmitError("")
    setSubmitNotice("")
    setStage("submitting")
    try {
      const res = inputMode === "text"
        ? await submitAnswerText(problem.id, textAnswer, studentName, studentId || undefined, finalAnswer || undefined)
        : await submitImageAnswer()
      setSubmissionId(res.submission_id)
      setTextAnswer("")
      setFinalAnswer("")
      setImageFile(null)
      setProblem(null)
      setSubmitNotice("제출되었습니다. 다른 문제를 풀어도 됩니다.")
      if (studentId) {
        loadSidebar(studentId)
      }
      setStage("problem")
    } catch (e: unknown) {
      setSubmitError(e instanceof Error ? e.message : "제출 실패")
      setStage("answer")
    }
  }

  async function submitImageAnswer() {
    if (!problem || !imageFile) {
      throw new Error("이미지를 선택해주세요")
    }
    return submitAnswerImage(problem.id, imageFile, studentName, studentId || undefined, finalAnswer || undefined)
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

  function reset() {
    setProblem(null)
    setTextAnswer("")
    setFinalAnswer("")
    setImageFile(null)
    setResult(null)
    setSubmissionId(null)
    setSubmitError("")
    setSubmitNotice("")
    if (studentId) {
      loadSidebar(studentId)
    }
    setStage("problem")
  }

  function handleLogout() {
    clearStudentSession()
    setStudentName("")
    setStudentId("")
    setHistory([])
    setHomework([])
    setProblem(null)
    setTextAnswer("")
    setFinalAnswer("")
    setImageFile(null)
    setResult(null)
    setSubmissionId(null)
    setSubmitNotice("")
    setSelectedHistory(null)
    setDetailResult(null)
    setStage("info")
  }

  return {
    stage,
    setStage,
    history,
    homework,
    studentName,
    setStudentName,
    studentId,
    setStudentId,
    finalAnswer,
    setFinalAnswer,
    problem,
    setProblem,
    textAnswer,
    setTextAnswer,
    setImageFile,
    setInputMode,
    result,
    submitError,
    submitNotice,
    selectedHistory,
    setSelectedHistory,
    detailResult,
    setDetailResult,
    problemTab,
    setProblemTab,
    homeworkLoading,
    setHomeworkLoading,
    loadSidebar,
    handleSubmit,
    loadDetail,
    reset,
    handleLogout,
  }
}
