# Benchmark Concurrency SLA Report (2026-04-13)

## Scope

- 목적: 동시 제출 상황에서 파이프라인 SLA 충족 여부 확인
- 데이터:
  - `tests/benchmark_pipeline_20260413_181527.csv`
  - `tests/benchmark_pipeline_20260413_182003.csv`
- 총 샘플: 12 submissions

## SLA Targets

- Grading Latency: `<= 1s`
- Feedback Total Latency: `<= 30s`
- Hallucination Latency: `<= 30s`

## Concurrency Results

| Concurrent Users | Samples | Completed (feedback+hallucination) | Grading SLA | Feedback SLA | Hallucination SLA | Feedback p50 / p95 / max (s) | Hallucination p50 / p95 / max (s) | Queue Peak (feedback_pending / feedback_running / hallucination_pending) |
|---|---:|---:|---:|---:|---:|---|---|---|
| 1 | 2 | 2/2 (100%) | 2/2 | 2/2 | 2/2 | 20.065 / 24.049 / 24.491 | 11.651 / 11.916 / 11.945 | 1 / 1 / 0 |
| 2 | 4 | 4/4 (100%) | 4/4 | 0/4 | 0/4 | 57.418 / 71.298 / 73.630 | 43.063 / 49.034 / 49.460 | 2 / 1 / 1 |
| 3 | 6 | 6/6 (100%) | 6/6 | 1/6 | 0/6 | 56.939 / 69.377 / 71.191 | 49.614 / 56.263 / 56.756 | 3 / 1 / 2 |

## Overall SLA Pass Rate

- Grading: `12/12` (100%)
- Feedback: `3/12` (25%)
- Hallucination: `2/12` (16.7%)

## Interpretation

- 안정성 측면(완료율/오류)은 양호:
  - errors: 0
  - timeout/OOM: 0
- 성능 SLA 측면:
  - `users >= 2`에서 Feedback/Hallucination SLA가 크게 미달
  - queue peak에서 `feedback_running=1`로 고정되어 worker 처리량이 병목으로 관찰됨

## Conclusion

- 현재 구성에서 SLA를 안정적으로 만족하는 동시성은 사실상 `1명` 수준.
- 목표(Feedback/Hallucination `<=30s`) 달성을 위해 worker concurrency/처리량 조정이 필요.
