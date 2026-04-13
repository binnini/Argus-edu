# 프론트엔드 구조 (현재 구현 기준)

Argus 프론트엔드는 React + Vite + TypeScript 기반이며 학생/교사 화면이 하나의 SPA로 구성됩니다.

## 기술 스택

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Radix UI 기반 컴포넌트
- KaTeX (`react-katex`)

## 라우팅

- `/student` → 학생 화면
- `/teacher` → 교사 화면
- 그 외 경로 → `/student` 리다이렉트

구현: `frontend/src/main.tsx`

## 학생 화면

메인: `frontend/src/pages/StudentPage.tsx`
상태 훅: `frontend/src/hooks/useStudentSubmission.ts`

### 상태 전이

`Stage` 값:
- `info`
- `problem`
- `answer`
- `submitting`
- `polling`
- `done`
- `detail`

동작 요약:
1. 학생 세션이 없으면 `info`에서 로그인/회원가입/게스트 시작
2. 문제 선택(`problem`) 후 답안 작성(`answer`)
3. 제출 중(`submitting`) 후 기본적으로 문제 화면으로 복귀
4. 백그라운드 폴링으로 완료 감지
5. 이력 상세 보기 시 `detail`

### 입력 방식

`AnswerInput` 탭:
- 이미지 업로드
- 카메라 촬영
- 직접 그리기 (`CanvasInput`, `CANVAS_ENABLED`일 때만)
- 샘플 이미지 (`VITE_ENABLE_SAMPLE_IMAGE_INPUT=true`일 때만)

샘플 이미지 API:
- `GET /api/v1/prototype/problem-sample-images`
- `GET /api/v1/prototype/sample-images/{sample_id}/content`

동작 규칙:
- 학생 문제 선택에서 `정답 샘플 있는 문제만` 필터를 사용할 수 있음
- 샘플 탭은 문제 기준 최대 3장 표시
- 정답 이미지가 존재하면 반드시 1장 포함
- 정답 이미지 선택 시 `최종 답` 입력란 자동 채움

## 교사 화면

메인: `frontend/src/pages/TeacherPage.tsx`

로그인:
- `PasswordGate`가 `/api/v1/teacher/queue`로 비밀번호 검증
- 성공 시 `localStorage['argus_teacher_pw']` 저장

탭 구성:
- 문제 관리 (`ProblemManager`)
- 풀이 현황 (`SubmissionOverview`)
- 검토 큐 (`ReviewQueue`)
- 작업 큐 (`QueueDashboard`)
- 그룹 관리 (`GroupManager`)
- 숙제 관리 (`HomeworkManager`)

## API 계층

- `src/api/client.ts`: 공통 fetch 래퍼, `API_BASE` 처리, 교사 헤더
- `src/api/submissions.ts`: 학생 제출/조회/숙제/샘플
- `src/api/teacher.ts`: 교사 큐/액션/문제/그룹/숙제

기본 API 경로:
- `VITE_API_BASE` 미설정 시 `/api/v1`

## 세션/저장소

학생 세션 (`sessionStorage`):
- `argus_student_name`
- `argus_student_id`

교사 비밀번호 (`localStorage`):
- `argus_teacher_pw`

## 주요 UI 컴포넌트

학생:
- `StudentInfoForm`
- `ProblemSelector`
- `HomeworkTab`
- `AnswerInput`
- `GradingStatus`
- `FeedbackPanel`

교사:
- `PasswordGate`
- `ReviewQueue`
- `ReviewCard`
- `QueueDashboard`
- `ProblemManager`
- `SubmissionOverview`
- `GroupManager`
- `HomeworkManager`

## 개발 실행

```bash
cd frontend
npm ci
npm run dev
```

개발 서버: `http://localhost:5173`
