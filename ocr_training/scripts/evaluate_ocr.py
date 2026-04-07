"""
Step 4: 파인튜닝 모델 vs 기본 GOT-OCR 모델 CER 비교
결과: ocr_training/output/evaluation_results.json
"""
import json
import random
from pathlib import Path

import torch
import Levenshtein
from PIL import Image
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = Path.home() / "projects/Argus-edu"
BASE_MODEL   = "stepfun-ai/GOT-OCR2_0"
TUNED_MODEL  = BASE / "ocr_training/output/got_ocr_finetuned"
TEST_DATA    = BASE / "data/ocr_samples/dataset/test.jsonl"
OUTPUT_JSON  = BASE / "ocr_training/output/evaluation_results.json"
OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

SAMPLE_N = 1000


def cer(pred: str, ref: str) -> float:
    if not ref:
        return 0.0
    return Levenshtein.distance(pred, ref) / len(ref)


def load_model(model_path: str):
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    model.eval()
    return model, tokenizer


def run_ocr(model, tokenizer, image_path: str) -> str:
    try:
        image = Image.open(image_path).convert("RGB")
        result = model.chat(tokenizer, image, ocr_type="format")
        return result.strip() if result else ""
    except Exception as e:
        return f"[ERROR: {e}]"


def evaluate(model, tokenizer, records: list[dict]) -> dict:
    cer_scores = []
    exact_matches = 0

    for rec in records:
        ref = rec["conversations"][1]["value"]
        pred = run_ocr(model, tokenizer, rec["image"])
        c = cer(pred, ref)
        cer_scores.append(c)
        if pred == ref:
            exact_matches += 1

    return {
        "mean_cer": sum(cer_scores) / len(cer_scores),
        "exact_match_rate": exact_matches / len(cer_scores),
        "sample_count": len(cer_scores),
    }


def main():
    with open(TEST_DATA) as f:
        records = [json.loads(line) for line in f]

    random.seed(42)
    sample = random.sample(records, min(SAMPLE_N, len(records)))
    print(f"평가 샘플: {len(sample):,}개")

    print("\n[1/2] 기본 GOT-OCR 2.0 평가 중...")
    base_model, base_tok = load_model(BASE_MODEL)
    base_results = evaluate(base_model, base_tok, sample)
    print(f"  CER: {base_results['mean_cer']:.4f} | Exact Match: {base_results['exact_match_rate']:.4f}")

    del base_model
    torch.cuda.empty_cache()

    print("\n[2/2] 파인튜닝 모델 평가 중...")
    tuned_model, tuned_tok = load_model(str(TUNED_MODEL))
    tuned_results = evaluate(tuned_model, tuned_tok, sample)
    print(f"  CER: {tuned_results['mean_cer']:.4f} | Exact Match: {tuned_results['exact_match_rate']:.4f}")

    results = {
        "base_model":   {"model": BASE_MODEL,        **base_results},
        "tuned_model":  {"model": str(TUNED_MODEL),  **tuned_results},
        "cer_improvement": base_results["mean_cer"] - tuned_results["mean_cer"],
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nCER 개선: {results['cer_improvement']:.4f}")
    print(f"결과 저장: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
