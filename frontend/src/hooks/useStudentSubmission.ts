// Student submission state and side effects.

import * as React from "react"

import {
  getSubmissionStatus,
  getStudentHistory,
  getStudentHomework,
  submitAnswerImage,
  submitAnswerText,
  updateSubmission,
  type Problem,
  type SubmissionStatusResponse,
  type StudentHistoryItem,
  type StudentHomeworkItem,
} from "@/api/submissions"
import { clearStudentSession, getStudentSession, hasStudentSession } from "@/lib/session"

export type Stage = "info" | "problem" | "answer" | "submitting" | "polling" | "done" | "detail" | "editing"

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
  const [selectedHistory, setSelectedHistory] = React.useState<StudentHistoryItem | null>(null)
  const [detailResult, setDetailResult] = React.useState<SubmissionStatusResponse | null>(null)
  const [editAnswer, setEditAnswer] = React.useState("")
  const [editError, setEditError] = React.useState("")
  const [editSubmitting, setEditSubmitting] = React.useState(false)
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
    if (stage !== "polling" || submissionId === null) return
    const interval = setInterval(async () => {
      try {
        const status = await getSubmissionStatus(submissionId)
        if (status.status !== "pending") {
          setResult(status)
          setStage("done")
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
    setStage("submitting")
    try {
      const res = inputMode === "text"
        ? await submitAnswerText(problem.id, textAnswer, studentName, studentId || undefined, finalAnswer || undefined)
        : await submitImageAnswer()
      setSubmissionId(res.submission_id)
      setStage("polling")
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
    setFinalAnswer("")
    setImageFile(null)
    setResult(null)
    setSubmissionId(null)
    setSubmitError("")
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
    selectedHistory,
    setSelectedHistory,
    detailResult,
    setDetailResult,
    editAnswer,
    setEditAnswer,
    editError,
    setEditError,
    editSubmitting,
    problemTab,
    setProblemTab,
    homeworkLoading,
    setHomeworkLoading,
    loadSidebar,
    handleSubmit,
    loadDetail,
    handleEditSubmit,
    reset,
    handleLogout,
  }
}
