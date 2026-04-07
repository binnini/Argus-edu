# Phase 6 통합 테스트 결과

실행일: 2026-04-07  
환경: Python 3.11, pytest 9.0.2, pytest-timeout 2.4.0  
백엔드: http://localhost:8000  
LLM: Ollama gemma4:26b (http://192.168.219.101:11434)

---

## 요약

| 항목 | 결과 |
|---|---|
| 전체 테스트 수 | 10 |
| **통과** | **7** |
| **실패** | **3** |
| 실패 원인 | macOS 로컬 네트워크 접근 권한 차단 |

---

## 테스트별 결과

| 테스트 | 상태 | 비고 |
|---|---|---|
| test_health | ✅ PASS | SBERT/HHEM 모두 true |
| test_problems_list | ✅ PASS | 15개 문제 확인 |
| test_problem_no_answer_leak | ✅ PASS | answer/reference_solution 미노출 확인 |
| test_teacher_auth_missing | ✅ PASS | 헤더 없음 → 401 |
| test_teacher_auth_wrong | ✅ PASS | 틀린 비밀번호 → 401 |
| test_e2e_normal_flow | ❌ FAIL | Ollama 연결 실패 (환경 문제) |
| test_e2e_low_trust | ❌ FAIL | Ollama 연결 실패 (환경 문제) |
| test_explanation_blocked_before_approval | ✅ PASS | graded 전 explanation=None 확인 |
| test_teacher_modify | ❌ FAIL | Ollama 연결 실패 (환경 문제) |
| test_feedback_summary | ✅ PASS | 필수 필드 및 값 범위 확인 |

---

## 실패 원인 분석

### macOS 로컬 네트워크 접근 권한 차단

- **현상**: Python `socket` / `httpx` / `asyncio.open_connection`으로 `192.168.219.101:11434` 연결 시 `OSError: [Errno 65] No route to host` 발생
- **curl은 정상**: curl(시스템 바이너리)로는 동일 엔드포인트 연결 및 응답 확인됨
- **근본 원인**: macOS 15(Sequoia)의 **로컬 네트워크 접근 제어** — Python.framework 바이너리가 LAN(192.168.x.x) 접근 권한을 얻지 못한 상태
- **백엔드 로그 확인**:
  ```
  openai._base_client: Retrying request to /chat/completions in 0.39s
  openai._base_client: Retrying request to /chat/completions in 0.91s
  routers.submissions: 채점 파이프라인 오류: LLM API 오류: Connection error.
  ```

### 해결 방법

```
System Preferences → Privacy & Security → Local Network
→ Python / Terminal 앱 허용 체크
```

또는 macOS 터미널에서:
```bash
# Python 앱의 로컬 네트워크 권한 초기화 후 재시도
tccutil reset LocalNetwork
```

---

## 검증된 기능 (7개 테스트 통과 기준)

- `/health` 엔드포인트: SBERT + HHEM 정상 로드
- `/api/v1/problems`: 15개 문제 전체 목록 반환
- `/api/v1/problems/{id}`: `answer` / `reference_solution` 학생 노출 차단 (HITL 보안 정책)
- `X-Teacher-Password` 인증: 헤더 없음 / 틀린 비밀번호 모두 401 반환
- `/api/v1/teacher/feedback/summary`: 필수 필드(`total_reviewed`, `approval_rate` 등) 정상 반환
- 승인 전 `explanation=None` 차단 정책: error 상태에서도 explanation 미노출 확인

---

## 로컬 네트워크 권한 해결 후 예상 결과

Ollama 연결이 복구되면 E2E 테스트 3개가 다음을 검증:
- 정답 제출 → graded → 교사 승인 → explanation 노출 전체 흐름
- 오답 제출 → low trust 분류 → full_review 큐 배치 (soft assert)
- 교사 수정(modify) 액션 → approved 상태 + 교사 점수 반영
