# Argus — Phase 1 & Phase 2 구현 진행 상황

> 기준일: 2026-04-06  
> 브랜치: `feat/phase1-phase2-implementation`

---

## 완료 현황

| Phase | 항목 | 상태 | 커밋 |
|---|---|---|---|
| 1-1 | 미분 문제 6개 (`math2_differentiation.json`) | 완료 | `c34164e` |
| 1-1 | 적분 문제 4개 (`math2_integration.json`) | 완료 | `c34164e` |
| 1-1 | 확통 문제 5개 (`stats_probability.json`) | 완료 | `c34164e` |
| 1-1 | 테스트 샘플 (`sample_submissions.json`) | 완료 | `c34164e` |
| 1-2 | SQLAlchemy ORM 모델 5종 | 완료 | `869a5aa` |
| 1-2 | Alembic 초기화 + 마이그레이션 파일 | 완료 | `869a5aa` |
| 1-2 | `scripts/seed.py` | 완료 | `869a5aa` |
| 1-3 | Pydantic 스키마 (problems/submissions/teacher) | 완료 | `cfda684` |
| 1-3 | `backend/config.py` (환경변수 로딩) | 완료 | `cfda684` |
| 1-3 | `backend/db.py` (async 세션 의존성 주입) | 완료 | `cfda684` |
| 2-1 | `backend/services/grading.py` | 완료 | `592ad4e` |
| 2-2 | `backend/services/explanation.py` | 완료 | `ec8f5b5` |
| 2-3 | Vite + React + TS scaffold | 완료 | `e842ab6` |
| 2-3 | `frontend/src/api/submissions.ts` | 완료 | `e842ab6` |
| 2-3 | `frontend/src/api/teacher.ts` | 완료 | `e842ab6` |
| 2-3 | `StudentSubmit.tsx` | 완료 | `e842ab6` |
| 2-3 | `TeacherDashboard.tsx` | 완료 | `e842ab6` |

---

## 생성된 파일 구조

```
Argus/
├── .env.example                          # 전체 환경변수 목록
├── data/
│   ├── problems/
│   │   ├── math2_differentiation.json   # 미분 문제 6개
│   │   ├── math2_integration.json       # 적분 문제 4개
│   │   └── stats_probability.json       # 확통 문제 5개
│   └── test_answers/
│       └── sample_submissions.json      # E2E 테스트용 학생 답변 샘플
├── backend/
│   ├── requirements.txt
│   ├── config.py                        # pydantic-settings 기반 환경변수 로딩
│   ├── db.py                            # async 세션 + get_session() 의존성 주입
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial_schema.py
│   ├── models/
│   │   ├── base.py
│   │   ├── problem.py
│   │   ├── submission.py
│   │   ├── grading_result.py
│   │   ├── teacher_queue.py
│   │   └── feedback_log.py
│   ├── schemas/
│   │   ├── problems.py
│   │   ├── submissions.py
│   │   └── teacher.py
│   └── services/
│       ├── grading.py                   # Claude API + SBERT 채점
│       └── explanation.py              # 멀티 샘플링 3회 + 불일치율
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx                     # React Router 설정
│       ├── api/
│       │   ├── submissions.ts           # 학생 제출 API 클라이언트
│       │   └── teacher.ts              # 교사 대시보드 API 클라이언트
│       └── pages/
│           ├── StudentSubmit.tsx        # 문제 선택 + 제출 + 결과 폴링
│           └── TeacherDashboard.tsx     # 검토 큐 + 승인/수정/거부 폼
└── scripts/
    └── seed.py                          # JSON → DB 삽입 스크립트
```

---

## 주요 설계 결정

### CLAUDE.md 절대 제약 준수
- **풀이 설명 자동 승인 없음**: `teacher_approved === true`일 때만 프론트에서 노출
- **모델명 하드코딩 없음**: `config.py`의 `grading_model`, `explanation_model`은 환경변수 우선

### 스킵 항목 (이유 기록)
- **로컬 DB 마이그레이션 실행**: 규칙에 따라 코드만 작성 (alembic upgrade head 명령어 미실행)
- **샘플 수동 검증 (2-1, 2-2)**: API 키 없이 실행 불가 → Phase 4 API 라우터 연결 후 통합 검증 예정

### 프론트엔드 scaffold 방식
- `vite create`가 기존 `frontend/` 디렉토리로 인해 자동 취소 → 필요 파일 수동 작성
- `frontend/CLAUDE.md`는 기존 파일 유지

---

## 다음 단계 (Phase 3)

Phase 3은 2-1, 2-2 완료 후 시작:

1. `backend/main.py` — lifespan 이벤트에서 HHEM + SBERT 1회 로드
2. `backend/services/hallucination.py` — HHEM-2.1-Open 팩추얼 일관성 스코어
3. `backend/services/trust_gate.py` — 종합 신뢰도 계산 + 큐 라우팅
