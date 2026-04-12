// Student sessionStorage helpers.

const STUDENT_NAME_KEY = "argus_student_name"
const STUDENT_ID_KEY = "argus_student_id"

export interface StudentSession {
  name: string
  id: string
}

export function getStudentSession(): StudentSession {
  return {
    name: sessionStorage.getItem(STUDENT_NAME_KEY) ?? "",
    id: sessionStorage.getItem(STUDENT_ID_KEY) ?? "",
  }
}

export function saveStudentSession(name: string, id: string): void {
  sessionStorage.setItem(STUDENT_NAME_KEY, name)
  sessionStorage.setItem(STUDENT_ID_KEY, id)
}

export function hasStudentSession(): boolean {
  return Boolean(sessionStorage.getItem(STUDENT_NAME_KEY))
}

export function clearStudentSession(): void {
  sessionStorage.removeItem(STUDENT_NAME_KEY)
  sessionStorage.removeItem(STUDENT_ID_KEY)
}
