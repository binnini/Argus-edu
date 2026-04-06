# Frontend — 개발 규칙

React + Vite (TypeScript). 루트 CLAUDE.md의 제약이 모두 적용됨.

## 프로젝트 구조

```
frontend/src/
├── pages/
│   ├── StudentSubmit.tsx     # 학생 답변 제출 화면 (라우트: /student)
│   └── TeacherDashboard.tsx  # 교사 검토 대시보드 (라우트: /teacher)
├── components/
│   ├── SubmissionForm.tsx    # 문제 표시 + 답변 입력
│   ├── GradingResult.tsx     # 채점 결과 표시 (풀이 설명은 승인 후만)
│   ├── ReviewQueue.tsx       # 교사 검토 큐 목록
│   ├── ReviewCard.tsx        # 개별 검토 카드 (승인/수정/거부)
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

### API 호출 중앙화

모든 API 호출은 `api/` 폴더에서만. 컴포넌트에서 직접 fetch/axios 금지.

```typescript
// api/submissions.ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export async function submitAnswer(payload: SubmissionRequest): Promise<SubmissionResponse> {
  const res = await fetch(`${API_BASE}/submissions`, { method: "POST", ... });
  ...
}
```

### 풀이 설명 노출 규칙

```tsx
// 풀이 설명은 teacher_approved === true 일 때만 렌더링
{result.teacher_approved && <ExplanationPanel explanation={result.explanation} />}
```

`teacher_approved`가 false/null이면 "교사 검토 중입니다" 메시지만 표시. 풀이 내용 절대 노출 금지.

### 교사 액션 (3가지만)

```tsx
type TeacherAction = "approve" | "modify" | "reject";
```

액션 없이 큐가 넘어가는 UI 패턴 금지. 반드시 명시적 선택 후 제출.

### 환경변수

```
VITE_API_BASE=http://localhost:8000/api/v1
```
