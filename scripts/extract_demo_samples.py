#!/usr/bin/env python3
"""Build demo image subset from AI-HUB handwriting validation zips.

Selection rule:
- School level: 초/중/고 each up to 100 images
- Per-domain cap: max 3
- Uses only handwriting explanation images (VS_3 + VL_3 pair)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "data" / "AI_HUB" / "3.개방데이터" / "1.데이터" / "Validation" / "01.원천데이터"
DEFAULT_LABEL_DIR = ROOT / "data" / "AI_HUB" / "3.개방데이터" / "1.데이터" / "Validation" / "02.라벨링데이터"
DEFAULT_OUTPUT_DIR = ROOT / "demo" / "images"


def school_level_from_name(name: str) -> str | None:
    if "초등학교" in name:
        return "초등학교"
    if "중학교" in name:
        return "중학교"
    if "고등학교" in name:
        return "고등학교"
    return None


def safe_domain(domain: str) -> str:
    return (
        domain.replace("/", "-")
        .replace("\\", "-")
        .replace(" ", "_")
        .strip()[:80]
        or "기타"
    )


def parse_json_bytes(raw: bytes) -> dict:
    # utf-8-sig: handles BOM
    return json.loads(raw.decode("utf-8-sig"))


def pick_for_school(candidates: list[dict], target: int, domain_cap: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        by_domain[c["domain"]].append(c)

    selected: list[dict] = []
    selected_keys: set[str] = set()
    domain_counts: dict[str, int] = defaultdict(int)
    for domain in sorted(by_domain.keys()):
        pool = by_domain[domain][:]
        rng.shuffle(pool)
        for item in pool[:domain_cap]:
            key = item["uid"]
            selected.append(item)
            selected_keys.add(key)
            domain_counts[item["domain"]] += 1

    if len(selected) < target:
        remainder = [c for c in candidates if c["uid"] not in selected_keys]
        rng.shuffle(remainder)
        for item in remainder:
            if len(selected) >= target:
                break
            if domain_counts[item["domain"]] >= domain_cap:
                continue
            selected.append(item)
            selected_keys.add(item["uid"])
            domain_counts[item["domain"]] += 1

    if len(selected) > target:
        rng.shuffle(selected)
        selected = selected[:target]

    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--label-dir", default=str(DEFAULT_LABEL_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--per-school", type=int, default=100)
    parser.add_argument("--per-domain", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260413)
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    label_dir = Path(args.label_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    label_zips = sorted(label_dir.glob("VL_3.손글씨풀이_*.zip"))
    if not label_zips:
        raise RuntimeError(f"No label zip found in {label_dir}")

    candidates_by_school: dict[str, list[dict]] = defaultdict(list)

    for label_zip in label_zips:
        school_level = school_level_from_name(label_zip.name)
        if school_level is None:
            continue

        source_zip = source_dir / label_zip.name.replace("VL_", "VS_")
        if not source_zip.exists():
            print(f"[skip] source zip missing for {label_zip.name}")
            continue

        with zipfile.ZipFile(label_zip, "r") as z_label, zipfile.ZipFile(source_zip, "r") as z_source:
            source_names = set(z_source.namelist())
            for name in z_label.namelist():
                if not name.lower().endswith(".json"):
                    continue
                try:
                    payload = parse_json_bytes(z_label.read(name))
                except Exception:
                    continue

                qinfo = (payload.get("question_info") or [{}])[0]
                domain = str(
                    qinfo.get("question_topic_name")
                    or qinfo.get("question_sector2")
                    or "기타"
                )
                exp_info = (payload.get("explanation_info") or [{}])[0]
                exp_filename = str(exp_info.get("explanation_filename") or "").strip()
                if not exp_filename:
                    continue
                source_member = exp_filename if exp_filename.startswith("/") else f"/{exp_filename}"
                if source_member not in source_names:
                    alt = source_member.lstrip("/")
                    if alt in source_names:
                        source_member = alt
                    else:
                        continue

                is_answer = "_O." in exp_filename.upper()
                uid = f"{label_zip.name}:{source_member}"
                candidates_by_school[school_level].append(
                    {
                        "uid": uid,
                        "school_level": school_level,
                        "domain": domain,
                        "domain_safe": safe_domain(domain),
                        "source_zip": str(source_zip),
                        "source_member": source_member,
                        "filename": Path(exp_filename).name,
                        "is_answer": is_answer,
                    }
                )

    manifest_samples: list[dict] = []
    school_order = ["초등학교", "중학교", "고등학교"]

    for idx, school_level in enumerate(school_order):
        candidates = candidates_by_school.get(school_level, [])
        if not candidates:
            print(f"[warn] no candidates for {school_level}")
            continue
        chosen = pick_for_school(
            candidates,
            target=args.per_school,
            domain_cap=args.per_domain,
            seed=args.seed + idx * 1000,
        )
        print(f"[pick] {school_level}: {len(chosen)}")

        zip_cache: dict[str, zipfile.ZipFile] = {}
        try:
            for item in chosen:
                zip_path = item["source_zip"]
                if zip_path not in zip_cache:
                    zip_cache[zip_path] = zipfile.ZipFile(zip_path, "r")
                z_source = zip_cache[zip_path]
                raw = z_source.read(item["source_member"])

                sample_key = f"{item['school_level']}|{item['domain']}|{item['filename']}|{item['uid']}"
                sample_id = hashlib.sha1(sample_key.encode("utf-8")).hexdigest()[:16]
                rel_path = Path(item["school_level"]) / item["domain_safe"] / f"{sample_id}_{item['filename']}"
                out_path = output_dir / rel_path
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(raw)

                manifest_samples.append(
                    {
                        "sample_id": sample_id,
                        "school_level": item["school_level"],
                        "domain": item["domain"],
                        "filename": item["filename"],
                        "relative_path": str(rel_path),
                        "is_answer": bool(item["is_answer"]),
                    }
                )
        finally:
            for z in zip_cache.values():
                z.close()

    manifest = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "source": {
            "source_dir": str(source_dir),
            "label_dir": str(label_dir),
            "per_school": args.per_school,
            "per_domain": args.per_domain,
            "seed": args.seed,
        },
        "samples": manifest_samples,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[done] samples={len(manifest_samples)} manifest={output_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
