# Argus — 교육자 Human-in-the-Loop 채점 시스템

한국 초·중·고 전과정 수학 서답형 자동 채점 + 교사 HITL 승인 파이프라인.

---

## 아키텍처 개요

```
학생 입력 (손글씨 이미지 또는 텍스트)
  → [OCR 엔진]          이미지 → 텍스트 변환 (MVP: AI-HUB 데이터 기반)
  → [채점 엔진]          LLM + SBERT 유사도
  → [개인화 피드백 생성] 학생 오류 분석 + 교정 방향 제시 (멀티 샘플링 3회)
  → [할루시네이션 탐지]  피드백이 학생의 실제 오류를 올바르게 짚었는지 검증
  → [신뢰도 게이트]      임계값 0.75
      High → 점수 즉시 노출 / 피드백 교사 큐
      Low  → 점수 + 피드백 모두 교사 큐
  → [교사 대시보드]      승인 / 수정 / 거부
  → [학생 최종 전달]     점수 + 교사 승인 개인화 피드백
  → [피드백 로그]        AI vs 교사 delta 저장
```

## 절대 제약 (예외 없음)

- **개인화 피드백 자동 승인 금지**: 신뢰도 High여도 반드시 교사 승인 후 노출
- **모델명 하드코딩 금지**: 반드시 환경변수로 분리 (`GRADING_MODEL`, `FEEDBACK_MODEL`, `OCR_MODEL`)
- **MVP 범위 외 구현 금지**: QA 기능, 회원가입, 실시간 손글씨 인식, 킬러 문항 지원

## AI 모델 구성

> 비용 최적화에 따라 모델은 변경될 수 있으므로 코드에 모델명을 직접 쓰지 말 것.

```python
GRADING_MODEL  = os.getenv("GRADING_MODEL", "claude-sonnet-4-6")
FEEDBACK_MODEL = os.getenv("FEEDBACK_MODEL", "claude-sonnet-4-6")
OCR_MODEL      = os.getenv("OCR_MODEL", "got_ocr")  # got_ocr | pix2tex | mathpix
```

## 기술 스택

| 레이어 | 기술 |
|---|---|
| 백엔드 | FastAPI (Python 3.11+) + PostgreSQL |
| OCR | GOT-OCR 2.0 파인튜닝 모델 (Mac Mini M4 MPS 서빙) |
| AI 채점 | Claude API + SBERT (all-MiniLM-L6-v2) |
| 개인화 피드백 | Claude API (학생 오류 분석 + 교정 방향 생성) |
| 할루시네이션 탐지 | SBERT 유사도 fallback (HF_TOKEN 설정 시 HHEM API) |
| 프론트엔드 | React + Vite (TypeScript) |
| 배포 | Mac Mini M4 (24GB) 직접 서빙 + Cloudflare Tunnel (ADR-019) |

## 성공 지표

- AI-교사 채점 일치율 ≥ 70%
- 피드백 오류 탐지 정밀도 ≥ 80%
- 교사 검토 1건당 평균 3분 이내
- 24시간 내 검토 완료율 ≥ 90%

## 상세 문서 위치

| 문서 | 경로 |
|---|---|
| DB 스키마 (전체 SQL) | `docs/schema.md` |
| API 요청/응답 스펙 | `docs/api.md` |
| 채점·피드백 프롬프트 템플릿 | `docs/prompts.md` |
| 데이터셋 구조 및 확보 전략 | `docs/dataset.md` |
| 주요 의사결정 기록 (ADR) | `docs/decisions.md` |
| 배포 절차 | `docs/deployment.md` |
