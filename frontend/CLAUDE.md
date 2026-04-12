# Frontend — 개발 규칙

React + Vite (TypeScript). 루트 CLAUDE.md의 제약이 모두 적용됨.

## 프로젝트 구조

```
frontend/src/
├── pages/
│   ├── StudentSubmit.tsx     # 학생 답변 제출 화면 (라우트: /student)
│   └── TeacherDashboard.tsx  # 교사 검토 대시보드 (라우트: /teacher)
├── components/
│   ├── AnswerInput.tsx       # 답변 입력 (텍스트 | 이미지 업로드 탭 전환)
│   ├── GradingResult.tsx     # 채점 결과 표시 (피드백은 승인 후만)
│   ├── FeedbackPanel.tsx     # 개인화 피드백 표시 (학생 오류 + 교정 방향)
│   ├── ReviewCard.tsx        # 교사 검토 카드 (승인/수정/거부)
│   └── TrustBadge.tsx        # 신뢰도 배지 (High/Low 표시)
└── api/
    ├── submissions.ts        # 학생 제출 API 호출
    └── teacher.ts            # 교사 대시보드 API 호출
```

## 라우팅

```tsx
<Route path="/student" element={<StudentSubmit />} />
<Route path="/teacher" element={<TeacherDashboard />} />
```

MVP는 두 화면만. 인증 라우트 가드는 teacher 진입 시 비밀번호 모달로 처리.

## 코딩 규칙

### 답변 입력 방식

MVP는 두 가지 입력 탭을 제공한다.

```tsx
// AnswerInput.tsx
type InputMode = "text" | "image";
```

- `text`: textarea 직접 입력
- `image`: 이미지 파일 업로드 (AI-HUB OCR 데이터 기반 테스트용)
- 향후 `canvas` 탭 추가 예정 (패드/핸드폰 손글씨 직접 그리기) — MVP 제외

이미지 업로드 시 `multipart/form-data`로 전송. 텍스트 입력 시 `application/json`.

### API 호출 중앙화

모든 API 호출은 `api/` 폴더에서만. 컴포넌트에서 직접 fetch/axios 금지.

```typescript
// api/submissions.ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export async function submitAnswerText(payload: TextSubmissionRequest): Promise<SubmissionResponse> { ... }
export async function submitAnswerImage(formData: FormData): Promise<SubmissionResponse> { ... }
```

### 개인화 피드백 노출 규칙

```tsx
// 피드백은 teacher_approved === true 일 때만 렌더링
{result.teacher_approved && <FeedbackPanel feedback={result.feedback} />}
```

`teacher_approved`가 false/null이면 "교사 검토 중입니다" 메시지만 표시. 피드백 내용 절대 노출 금지.

피드백 구조 (승인 후 노출):
```tsx
interface PersonalizedFeedback {
  student_mistakes: { step: number; description: string }[];  // 학생이 틀린 부분
  correct_approach: { step: number; title: string; content: string }[];  // 올바른 풀이
  key_concept: string;  // 핵심 개념 요약
}
```

### 교사 액션 (3가지만)

```tsx
type TeacherAction = "approve" | "modify" | "reject";
```

액션 없이 큐가 넘어가는 UI 패턴 금지. 반드시 명시적 선택 후 제출.

### 환경변수

```
VITE_API_BASE=http://localhost:8000/api/v1
```
