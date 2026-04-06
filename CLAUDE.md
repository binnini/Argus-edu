# Argus — 교육자 Human-in-the-Loop 채점 시스템

한국 고등학교 수학 서답형 자동 채점 + 교사 HITL 승인 파이프라인.

---

## 아키텍처 개요

```
학생 답변 제출
  → [채점 엔진]       Claude API + SBERT 유사도
  → [풀이 설명 생성]  멀티 샘플링 3회
  → [할루시네이션 탐지] HHEM-2.1-Open
  → [신뢰도 게이트]   임계값 0.75
      High → 채점 즉시 노출 / 풀이 교사 큐
      Low  → 채점 + 풀이 모두 교사 큐
  → [교사 대시보드]   승인 / 수정 / 거부
  → [학생 최종 전달]  채점 + 교사 승인 풀이
  → [피드백 로그]     AI vs 교사 delta 저장
```

## 절대 제약 (예외 없음)

- **풀이 설명 자동 승인 금지**: 신뢰도 High여도 반드시 교사 승인 후 노출
- **모델명 하드코딩 금지**: 반드시 환경변수로 분리 (`GRADING_MODEL`, `EXPLANATION_MODEL`)
- **MVP 범위 외 구현 금지**: QA 기능, 회원가입, 모바일 UI, 킬러 문항 지원

## AI 모델 구성

> 비용 최적화에 따라 모델은 변경될 수 있으므로 코드에 모델명을 직접 쓰지 말 것.

```python
GRADING_MODEL     = os.getenv("GRADING_MODEL", "claude-sonnet-4-6")
EXPLANATION_MODEL = os.getenv("EXPLANATION_MODEL", "claude-sonnet-4-6")
```

## 기술 스택

| 레이어 | 기술 |
|---|---|
| 백엔드 | FastAPI (Python 3.11+) + PostgreSQL |
| AI 채점 | Claude API + SBERT (all-MiniLM-L6-v2) |
| 할루시네이션 탐지 | HHEM-2.1-Open (HuggingFace, 메모리 상주) |
| 프론트엔드 | React + Vite (TypeScript) |
| 배포 | AWS EC2 t3.medium + Nginx + systemd |

## 성공 지표

- AI-교사 채점 일치율 ≥ 70%
- 할루시네이션 탐지 정밀도 ≥ 80%
- 교사 검토 1건당 평균 3분 이내
- 24시간 내 검토 완료율 ≥ 90%

## 상세 문서 위치

| 문서 | 경로 |
|---|---|
| DB 스키마 (전체 SQL) | `docs/schema.md` |
| API 요청/응답 스펙 | `docs/api.md` |
| 채점·풀이 프롬프트 템플릿 | `docs/prompts.md` |
| 데이터셋 구조 및 확보 전략 | `docs/dataset.md` |
| 주요 의사결정 기록 (ADR) | `docs/decisions.md` |
| 배포 절차 | `docs/deployment.md` |
