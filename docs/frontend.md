# 프론트엔드 설계

Argus 프론트엔드 구조, 라우팅, 컴포넌트 트리, 디자인 시스템, 상태 관리 규칙을 정의한다.  
**ADR-021** 기반 재설계. 구현 시 이 문서를 우선 기준으로 한다.

---

## 기술 스택

| 항목 | 선택 | 이유 |
|------|------|------|
| 번들러 | Vite + React 18 | 기존 유지 |
| 언어 | TypeScript | 기존 유지 |
| 스타일 | **Tailwind CSS v3** | 유틸리티 클래스, 다크모드 기본 지원 |
| 컴포넌트 | **shadcn/ui** | Radix UI 기반, 접근성 보장, 소스 소유 |
| 아이콘 | **Lucide React** | shadcn/ui 기본, 트리 셰이킹 |
| 수식 렌더링 | **KaTeX** (`react-katex`) | LaTeX 수식 지원 (문제 본문, 피드백) |
| 캔버스 | **react-signature-canvas** | 터치/마우스 입력, 가역적 의존성 |
| HTTP | Axios 또는 fetch (기존 유지) | — |

---

## 디자인 시스템

### 색상 팔레트

```
중립(배경/텍스트): Zinc  (zinc-50 ~ zinc-950)
액센트(주요 액션): Indigo (indigo-500 ~ indigo-700)
성공:             Emerald (emerald-500)
경고:             Amber   (amber-500)
오류:             Rose    (rose-500)
```

- 다크모드: `class` 전략 (`<html class="dark">`)
- 기본값: 라이트모드. 토글 버튼으로 전환.

### 타이포그래피

```css
/* 한국어 본문 */
font-family: 'Pretendard Variable', 'Pretendard', -apple-system, sans-serif;

/* 수식/코드 */
font-family: 'JetBrains Mono', 'Fira Code', monospace;
```

Pretendard는 CDN(`@fontsource/pretendard`) 또는 로컬 파일로 제공.

### 간격·반경

- 기본 반경: `rounded-xl` (12px) — 카드, 버튼
- 소형 반경: `rounded-lg` (8px) — 입력, 배지
- 간격 단위: Tailwind 기본 4px 그리드

### 컴포넌트 규칙

| 상황 | 사용 |
|------|------|
| 버튼 (주요 액션) | `Button variant="default"` (Indigo 배경) |
| 버튼 (보조) | `Button variant="outline"` |
| 버튼 (위험) | `Button variant="destructive"` (Rose) |
| 카드 컨테이너 | `Card` + `CardHeader` + `CardContent` |
| 탭 전환 | `Tabs` + `TabsList` + `TabsTrigger` + `TabsContent` |
| 입력 필드 | `Input`, `Textarea` |
| 선택 드롭다운 | `Select` |
| 상태 배지 | `Badge variant=` (default/outline/destructive) |
| 모달 | `Dialog` |
| 알림 | `Toast` (Sonner 또는 shadcn toast) |
| 로딩 | `Skeleton` + 스피너 (`Loader2` 아이콘, `animate-spin`) |

---

## 라우팅 구조

```
/                      → redirect → /student
/student               → StudentPage        학생 메인
/teacher               → TeacherPage        교사 메인 (비밀번호 게이트)
```

`main.tsx` React Router v6 설정.

---

## 페이지 · 컴포넌트 트리

### 학생 페이지 — `/student`

```
StudentPage
├── StudentInfoForm          이름·학번 입력 (제출 전 1회)
│     ├── Input (이름)
│     └── Input (학번, optional)
├── ProblemSelector          문제 선택 드롭다운
│     └── Select
├── AnswerInput              답변 입력 탭 (3탭)
│     ├── Tab: 이미지 업로드
│     │     ├── FileDropzone   드래그&드롭 또는 파일 선택
│     │     └── ImagePreview   미리보기 + 교체 버튼
│     ├── Tab: 카메라 촬영
│     │     └── <input capture="environment"> 버튼
│     └── Tab: 직접 그리기  [CANVAS_ENABLED=true 시만 노출]
│           └── CanvasInput   react-signature-canvas
│                 ├── 초기화 버튼
│                 └── 굵기·색상 선택
├── SubmitButton
├── GradingStatus            채점 진행 상태 (폴링)
│     ├── Skeleton (pending)
│     ├── ScoreBadge (graded, score_visible=true)
│     └── PendingReviewBanner (교사 검토 대기)
└── FeedbackPanel            교사 승인 후만 렌더링
      ├── MistakeList        student_mistakes
      ├── ApproachSteps      correct_approach (단계별)
      └── KeyConceptCard     key_concept
```

**StudentPage 상태 머신**

```
idle → info_input → problem_select → answer_input → submitting → polling → done
                                                         ↑              |
                                                         └── retry ←────┘ (error)
```

---

### 교사 페이지 — `/teacher`

```
TeacherPage
├── PasswordGate             비밀번호 입력 (미인증 시)
└── TeacherDashboard         인증 후 표시
      ├── DashboardHeader    로그아웃·통계 요약 바
      └── Tabs
            ├── Tab: 문제 관리
            │     └── ProblemManager
            │           ├── ProblemTable       문제 목록 (제목·도메인·난이도·제출수)
            │           ├── ProblemFormDialog  등록·수정 모달
            │           │     ├── Input (제목)
            │           │     ├── Textarea (문제 본문, LaTeX 지원)
            │           │     ├── Input (정답)
            │           │     ├── Textarea (참조 풀이)
            │           │     ├── RubricEditor  단계별 배점 입력
            │           │     ├── Select (도메인)
            │           │     └── Select (난이도 1-5)
            │           └── DeleteConfirmDialog
            ├── Tab: 풀이 현황
            │     └── SubmissionOverview
            │           ├── FilterBar          문제·상태·날짜 필터
            │           ├── SubmissionTable     학생명·학번·문제·점수·상태·제출시각
            │           └── SubmissionDetailDialog  풀이 이미지·OCR 원문·채점 결과 조회
            └── Tab: 검토 큐
                  └── ReviewQueue
                        ├── QueueStats         미처리·SLA 임박 카운트
                        ├── TrustFilter        High/Low 필터 토글
                        └── ReviewCard[]       기존 ReviewCard.tsx 재사용
                              ├── TrustBadge
                              ├── StudentAnswer
                              ├── AIFeedbackPreview
                              └── ActionButtons  (승인·수정·거부)
```

---

## API 연동 패턴

```
src/api/
├── submissions.ts    학생 제출·폴링
├── teacher.ts        교사 큐·액션·통계
└── problems.ts       문제 조회(학생) + CRUD(교사)
```

- 모든 API 함수는 `async` / 에러 시 `throw`
- 교사 API: `X-Teacher-Password` 헤더를 API 함수 내부에서 `localStorage`에서 읽어 첨부
- 폴링: `useEffect` + `setInterval` (2초 간격), 컴포넌트 언마운트 시 `clearInterval`

---

## 상태 관리

**전역 상태 없음** — 페이지 단위 `useState` / `useReducer`만 사용.

| 데이터 | 위치 |
|--------|------|
| 교사 비밀번호 | `localStorage` ('argus_teacher_pw') |
| 학생 이름·학번 | `sessionStorage` + `useState` (StudentPage) |
| 문제 목록 캐시 | `useState` + 마운트 시 1회 fetch |
| 채점 폴링 상태 | `useState` (StudentPage 내부) |

---

## 파일 구조

```
frontend/src/
├── main.tsx
├── pages/
│   ├── StudentPage.tsx          (기존 StudentSubmit.tsx 대체)
│   └── TeacherPage.tsx          (기존 TeacherDashboard.tsx 대체)
├── components/
│   ├── student/
│   │   ├── StudentInfoForm.tsx
│   │   ├── ProblemSelector.tsx
│   │   ├── AnswerInput.tsx      (3탭 확장)
│   │   ├── CanvasInput.tsx      (신규, 가역적)
│   │   ├── GradingStatus.tsx
│   │   └── FeedbackPanel.tsx   (기존 유지)
│   ├── teacher/
│   │   ├── PasswordGate.tsx
│   │   ├── DashboardHeader.tsx
│   │   ├── ProblemManager.tsx
│   │   ├── ProblemFormDialog.tsx
│   │   ├── RubricEditor.tsx
│   │   ├── SubmissionOverview.tsx
│   │   ├── SubmissionDetailDialog.tsx
│   │   ├── ReviewQueue.tsx
│   │   └── ReviewCard.tsx      (기존 유지, 경로 이동)
│   └── ui/                     (shadcn/ui 생성 컴포넌트 — 수정 금지)
│       ├── button.tsx
│       ├── card.tsx
│       ├── tabs.tsx
│       └── ...
├── api/
│   ├── submissions.ts
│   ├── teacher.ts
│   └── problems.ts
├── lib/
│   └── utils.ts                (shadcn/ui cn() 유틸)
└── styles/
    └── globals.css             (Tailwind directives + CSS 변수)
```

---

## KaTeX 수식 렌더링 규칙

- 문제 본문(`content`)과 피드백 단계(`correct_approach.content`)에 LaTeX가 포함될 수 있다.
- `$...$` (인라인) 및 `$$...$$` (블록) 구문을 `react-katex`의 `InlineMath` / `BlockMath`로 변환.
- 파싱: 백엔드에서 오는 원본 문자열을 `$` 기준으로 분리하여 렌더링. 별도 Markdown 파서 불필요.

```tsx
// 예시
<BlockMath math="f'(x) = 3x^2 - 6x" />
<InlineMath math="x = 0 \text{ 또는 } x = 2" />
```

---

## 캔버스 입력 가역성 보장

`CanvasInput.tsx`는 `AnswerInput.tsx`에서만 사용된다.  
제거 절차:

```tsx
// AnswerInput.tsx 상단
const CANVAS_ENABLED = true   // ← false로 변경하면 탭 자체가 숨겨짐
```

```bash
# 완전 제거 시
rm frontend/src/components/student/CanvasInput.tsx
npm uninstall react-signature-canvas
```

백엔드 변경 없음. 기존 `POST /api/v1/submissions/image` 그대로 사용.

---

## 다크모드

- `<html>` 태그의 `class="dark"` 여부로 제어 (Tailwind `darkMode: 'class'`)
- `DashboardHeader` 또는 전역 헤더에 토글 버튼 배치
- 색상 변수는 `globals.css`의 CSS Custom Properties로 정의 (shadcn/ui 기본 방식)

---

## 반응형 레이아웃

| 브레이크포인트 | 레이아웃 |
|---|---|
| `sm` (640px 미만) | 단일 컬럼, 풀 너비 카드 |
| `md` (768px~) | 사이드 패딩 추가 |
| `lg` (1024px~) | 교사 대시보드: 탭 사이드바 레이아웃 가능 |

MVP 우선순위: 데스크톱(교사) + 모바일(학생 카메라 입력).
