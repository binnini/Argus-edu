import json
import random
from pathlib import Path

import torch
import Levenshtein
from peft import PeftModel
from transformers import AutoConfig, AutoTokenizer
from transformers.dynamic_module_utils import get_class_from_dynamic_module
from tqdm import tqdm

BASE       = Path.home() / "projects/Argus-edu"
BASE_MODEL = "stepfun-ai/GOT-OCR2_0"
LORA_PATH  = BASE / "ocr_training/output/got_ocr_finetuned_v2"
TEST_DATA  = BASE / "data/ocr_samples/dataset/test.jsonl"
OUTPUT_DIR = BASE / "ocr_training/output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_N = 1000

def cer(pred: str, ref: str) -> float:
    if not ref:
        return 0.0
    return Levenshtein.distance(pred, ref) / len(ref)

def load_base_model(lora_path=None):
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    config = AutoConfig.from_pretrained(BASE_MODEL, trust_remote_code=True)
    model_class = get_class_from_dynamic_module(config.auto_map["AutoModel"], BASE_MODEL)
    model = model_class.from_pretrained(
        BASE_MODEL,
        config=config,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model = model.to("cuda")

    if lora_path:
        print(f"LoRA 어댑터 로딩: {lora_path}")
        model = PeftModel.from_pretrained(model, str(lora_path))
        model = model.merge_and_unload()
        print("Merge 완료")

    if model.generation_config.pad_token_id is None:
        model.generation_config.pad_token_id = tokenizer.pad_token_id

    model.eval()
    return model, tokenizer

def run_ocr(model, tokenizer, image_path: str, ocr_type: str = "ocr") -> str:
    """model.chat() 방식 — base/fine-tuned 공통"""
    try:
        result = model.chat(tokenizer, image_path, ocr_type=ocr_type)
        return result.strip() if result else ""
    except Exception as e:
        return f"[ERROR: {e}]"

def evaluate(model, tokenizer, records: list[dict], ocr_type: str = "ocr") -> dict:
    cer_scores = []
    exact_matches = 0
    errors = 0

    for rec in tqdm(records, desc=f"평가 중 ({ocr_type})", unit="건"):
        ref = rec["conversations"][1]["value"]
        pred = run_ocr(model, tokenizer, rec["image"], ocr_type)
        if pred.startswith("[ERROR"):
            errors += 1
            continue
        c = cer(pred, ref)
        cer_scores.append(c)
        if pred == ref:
            exact_matches += 1

    return {
        "mean_cer": sum(cer_scores) / len(cer_scores) if cer_scores else 0,
        "exact_match_rate": exact_matches / len(cer_scores) if cer_scores else 0,
        "sample_count": len(cer_scores),
        "error_count": errors,
    }

def save_result(path: Path, results: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"저장: {path}")

BASE_RESULTS_PATH = OUTPUT_DIR / "base_model_results.json"

def main():
    with open(TEST_DATA) as f:
        records = [json.loads(line) for line in f]

    random.seed(42)
    sample = random.sample(records, min(SAMPLE_N, len(records)))
    print(f"평가 샘플: {len(sample):,}개")

    results = {}

    # 1. Base 모델 결과 로드 (이미 완료된 경우 재사용)
    if BASE_RESULTS_PATH.exists():
        print("\n[1/2] Base 결과 파일 로드 (재평가 생략)...")
        with open(BASE_RESULTS_PATH) as f:
            base_results = json.load(f)
        results.update(base_results)
        for ocr_type in ["ocr", "format"]:
            r = results[f"base_{ocr_type}"]
            print(f"  [{ocr_type}] CER: {r['mean_cer']:.4f} | EM: {r['exact_match_rate']:.4f} | n={r['sample_count']}")
    else:
        print("\n[1/2] Base GOT-OCR 2.0 평가...")
        base_model, base_tok = load_base_model(lora_path=None)
        for ocr_type in ["ocr", "format"]:
            r = evaluate(base_model, base_tok, sample, ocr_type)
            results[f"base_{ocr_type}"] = r
            print(f"  [{ocr_type}] CER: {r['mean_cer']:.4f} | EM: {r['exact_match_rate']:.4f} | n={r['sample_count']}")
        del base_model
        torch.cuda.empty_cache()

    # 2. Fine-tuned 모델 평가 (v2: chat() 포맷 정렬 학습)
    print("\n[2/2] Fine-tuned GOT-OCR 2.0 v2 평가...")
    ft_model, ft_tok = load_base_model(lora_path=LORA_PATH)
    for ocr_type in ["ocr", "format"]:
        r = evaluate(ft_model, ft_tok, sample, ocr_type)
        results[f"finetuned_{ocr_type}"] = r
        print(f"  [{ocr_type}] CER: {r['mean_cer']:.4f} | EM: {r['exact_match_rate']:.4f} | n={r['sample_count']}")

    # 결과 저장
    save_result(OUTPUT_DIR / "evaluation_comparison.json", results)

    # 요약 출력
    print("\n=== 결과 요약 ===")
    for ocr_type in ["ocr", "format"]:
        base = results[f"base_{ocr_type}"]
        ft   = results[f"finetuned_{ocr_type}"]
        cer_diff = base["mean_cer"] - ft["mean_cer"]
        print(f"\n[{ocr_type}]")
        print(f"  Base      CER: {base['mean_cer']:.4f} | EM: {base['exact_match_rate']:.4f}")
        print(f"  Finetuned CER: {ft['mean_cer']:.4f}  | EM: {ft['exact_match_rate']:.4f}")
        print(f"  CER 개선:      {cer_diff:+.4f} ({'개선' if cer_diff > 0 else '악화'})")

if __name__ == "__main__":
    main()
