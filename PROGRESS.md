# Argus — 진행 현황

> 최종 업데이트: 2026-04-07  
> 현재 브랜치: `docs/system-redesign`

---

## 완료된 Phase

| Phase | 내용 | 브랜치 | 커밋 |
|---|---|---|---|
| Phase 0 | 로컬 환경 세팅 (venv, DB, 마이그레이션, seed 15개) | feat/phase1-phase2-implementation | `fb6e5d5` |
| Phase 1 | 데이터셋, ORM 모델, Pydantic 스키마 | feat/phase1-phase2-implementation | `cfda684` |
| Phase 2 | grading/explanation 서비스, 프론트엔드 scaffold | feat/phase1-phase2-implementation | `ec8f5b5` |
| Phase 3 | HHEM 탐지, 신뢰도 게이트 | feat/phase1-phase2-implementation | `e69349e` |
| Phase 4 | API 라우터 11개 (submissions/teacher/feedback) | feat/phase1-phase2-implementation | `530b46e` |
| Phase 5 | 프론트엔드 실제 API 연동 (폴링, 교사 승인 흐름) | feat/phase5-frontend | `dda5d5d` |
| Phase 6 | 통합 테스트 10/10 통과 | feat/phase6-integration-test | `972ebe2` |
| Docs 개정 | 시스템 설계 전면 개정 (개인화 피드백 + OCR + AI-HUB) | docs/system-redesign | `22b3467` |

---

## 시스템 설계 변경 (2026-04-07)

Phase 1~6 완료 후 아래 사항으로 시스템 설계가 전면 변경됐다.

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 학생 입력 | 텍스트 직접 입력만 | 텍스트 + 이미지 업로드 (OCR) |
| AI 피드백 | 일반 풀이 설명 (reference_solution 기반) | 학생 오류 분석 + 교정 방향 개인화 피드백 |
| 할루시네이션 검증 대상 | 설명 vs 참조 풀이 비교 | 피드백이 학생의 실제 오류를 올바르게 짚었는지 |
| 데이터 소스 | 자체 생성 문제 15개 (품질 문제) | AI-HUB 수학 데이터셋 |

---

## Phase 6에서 발견·수정된 버그

| 버그 | 원인 | 수정 커밋 |
|---|---|---|
| macOS Local Network 차단 | uvicorn → WSL Ollama 연결 권한 없음 | socat LaunchAgent 등록 |
| JSON 파싱 실패 | Gemma4 LaTeX(`\frac`) → 잘못된 JSON escape | regex 정규화 후 재시도 |
| 교사 액션 500 | `score_delta` GENERATED ALWAYS 컬럼 직접 INSERT | SQLAlchemy `Computed` 타입으로 수정 |

---

## AI-HUB 데이터 현황

```
data/AI_HUB/3.개방데이터/1.데이터/
├── Training/
│   ├── 01.원천데이터/   ← 이미지 (TS_*.zip)
│   └── 02.라벨링데이터/ ← JSON (TL_*.zip)
│       ├── TL_1.문제_고등학교_공통수학.zip        ← 문제 텍스트 (LaTeX)
│       ├── TL_2.모범답안_고등학교_공통수학.zip     ← 모범답안 텍스트 (LaTeX)
│       └── TL_3.손글씨풀이_고등학교_공통수학.zip   ← 손글씨 풀이 이미지
└── Validation/ (동일 구조)
```

**AI-HUB JSON 주요 필드**:
- `question_text`: 문제 본문 (LaTeX `$...$` 형식)
- `answer_text`: 모범답안 풀이 (LaTeX, 연속 수식 나열)
- `question_difficulty`: 1~5 난이도
- `question_topic_name`: 단원명 (예: "다항식의 덧셈과 뺄셈")
- `question_type1`: "서술" (서술형)

---

## 현재 파일 구조

```
Argus/
├── .env
├── .env.example
├── .gitignore
├── CLAUDE.md                        # 시스템 헌법 (개정됨)
├── PROGRESS.md
├── TODO.md
├── proposal.md
├── data/
│   ├── AI_HUB/                      # AI-HUB 다운로드 데이터
│   ├── problems/                    # 기존 자체 생성 문제 (폐기 예정)
│   └── test_answers/
├── backend/
│   ├── CLAUDE.md                    # 백엔드 개발 규칙 (개정됨)
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── routers/
│   │   ├── submissions.py
│   │   ├── teacher.py
│   │   └── feedback.py
│   ├── services/
│   │   ├── grading.py
│   │   ├── explanation.py           # → feedback.py로 교체 예정
│   │   ├── hallucination.py
│   │   ├── trust_gate.py
│   │   └── llm_client.py
│   ├── models/
│   └── schemas/
├── frontend/
│   ├── CLAUDE.md                    # 프론트엔드 개발 규칙 (개정됨)
│   └── src/
│       ├── pages/
│       └── components/
├── tests/
│   ├── test_integration.py          # 통합 테스트 10개
│   └── results.txt
├── scripts/
│   └── seed.py
└── docs/
    ├── schema.md                    # DB 스키마 (개정됨)
    ├── api.md                       # API 스펙 (개정됨)
    ├── prompts.md                   # 프롬프트 템플릿 v2.0 (개정됨)
    ├── dataset.md                   # 데이터셋 전략 (개정됨)
    └── decisions.md                 # ADR-001~016 (개정됨)
```

---

## 다음 작업 (설계 변경 후)

1. `scripts/convert_aihub.py` — AI-HUB 원본 → Argus 스키마 변환
2. DB 마이그레이션 — `submissions` 테이블에 `input_type`, `ocr_raw_text`, `image_path` 추가
3. `backend/services/feedback.py` — 개인화 피드백 서비스 (explanation.py 교체)
4. `backend/services/ocr.py` — OCR 서비스 (pix2tex)
5. 프론트엔드 — `AnswerInput.tsx`, `FeedbackPanel.tsx` 추가
