#!/usr/bin/env python3
"""Summarize benchmark CSV outputs."""

from __future__ import annotations

import argparse
import csv
import glob
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

GRADING_TARGET_S = 1.0
FEEDBACK_TARGET_S = 30.0


def parse_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    rank = (len(sorted_vals) - 1) * p
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return sorted_vals[lo]
    frac = rank - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def resolve_files(patterns: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        matches = [Path(p) for p in glob.glob(pattern)]
        if matches:
            files.extend(matches)
        else:
            path = Path(pattern)
            if path.exists():
                files.append(path)
    unique = sorted(set(files))
    if not unique:
        raise RuntimeError("No CSV files matched input patterns")
    return unique


def summarize_group(name: str, rows: list[dict[str, str]]) -> None:
    total = len(rows)
    errors = [r for r in rows if (r.get("error") or "").strip()]
    oks = [r for r in rows if not (r.get("error") or "").strip()]
    oom_errors = [
        r for r in errors if "oom" in (r.get("error") or "").lower() or "out of memory" in (r.get("error") or "").lower()
    ]

    grading = [v for v in (parse_float(r.get("grading_latency_s")) for r in oks) if v is not None]
    feedback = [v for v in (parse_float(r.get("feedback_total_latency_s")) for r in oks) if v is not None]
    hallucination = [v for v in (parse_float(r.get("hallucination_latency_s")) for r in oks) if v is not None]
    memory_end = [v for v in (parse_float(r.get("memory_end_mb")) for r in rows) if v is not None]

    grading_pass = sum(1 for v in grading if v <= GRADING_TARGET_S)
    feedback_pass = sum(1 for v in feedback if v <= FEEDBACK_TARGET_S)

    print(f"\n[{name}]")
    print(
        f"rows={total} ok={len(oks)} errors={len(errors)} "
        f"error_rate={((len(errors) / total) * 100):.1f}% oom_errors={len(oom_errors)}"
    )
    if grading:
        print(
            "grading: "
            f"p50={percentile(grading, 0.50):.3f}s p95={percentile(grading, 0.95):.3f}s "
            f"max={max(grading):.3f}s pass={grading_pass}/{len(grading)}"
        )
    if feedback:
        print(
            "feedback: "
            f"p50={percentile(feedback, 0.50):.3f}s p95={percentile(feedback, 0.95):.3f}s "
            f"max={max(feedback):.3f}s pass={feedback_pass}/{len(feedback)}"
        )
    if hallucination:
        print(
            "hallucination: "
            f"p50={percentile(hallucination, 0.50):.3f}s p95={percentile(hallucination, 0.95):.3f}s "
            f"max={max(hallucination):.3f}s samples={len(hallucination)}"
        )
    if memory_end:
        print(f"memory_end_mb: max={max(memory_end):.2f} avg={(sum(memory_end) / len(memory_end)):.2f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "inputs",
        nargs="+",
        help='CSV file paths or glob patterns. Example: "tests/benchmark_*.csv"',
    )
    args = parser.parse_args()

    files = resolve_files(args.inputs)
    print("Files:")
    for file in files:
        print(f"- {file}")

    all_rows: list[dict[str, str]] = []
    by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    for file in files:
        with file.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_rows.append(row)
                by_scenario[row.get("scenario", "unknown")].append(row)

    summarize_group("all", all_rows)
    for scenario in sorted(by_scenario):
        summarize_group(scenario, by_scenario[scenario])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
