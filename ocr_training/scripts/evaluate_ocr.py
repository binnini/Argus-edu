import json
import random
from pathlib import Path

import torch
import Levenshtein
from PIL import Image
import torchvision.transforms as T
from peft import PeftModel
from transformers import AutoConfig, AutoTokenizer
from transformers.dynamic_module_utils import get_class_from_dynamic_module
from tqdm import tqdm

# 학습 시와 동일한 이미지 전처리
IMAGE_TRANSFORM = T.Compose([
    T.Resize((1024, 1024)),
    T.ToTensor(),
    T.Normalize(mean=[0.48145466, 0.4578275, 0.40821073],
                std=[0.26862954, 0.26130258, 0.27577711]),
])
MAX_NEW_TOKENS = 512

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

def run_ocr_chat(model, tokenizer, image_path: str, ocr_type: str = "ocr") -> str:
    """Base 모델용: model.chat() 방식"""
    try:
        result = model.chat(tokenizer, image_path, ocr_type=ocr_type)
        return result.strip() if result else ""
    except Exception as e:
        return f"[ERROR: {e}]"

def run_ocr_direct(model, tokenizer, image_path: str) -> str:
    """Fine-tuned 모델용: 학습 시와 동일한 images 텐서 방식"""
    try:
        image = Image.open(image_path).convert("RGB")
        images = IMAGE_TRANSFORM(image).unsqueeze(0).unsqueeze(0).to(dtype=torch.bfloat16, device="cuda")

        bos_id = tokenizer.bos_token_id or tokenizer.eos_token_id
        input_ids = torch.tensor([[bos_id]], device="cuda")

        with torch.no_grad():
            out = model.generate(
                input_ids=input_ids,
                images=images,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        generated = out[0, input_ids.shape[1]:]
        return tokenizer.decode(generated, skip_special_tokens=True).strip()
    except Exception as e:
        return f"[ERROR: {e}]"

def evaluate(model, tokenizer, records: list[dict], ocr_type: str = "ocr", use_direct: bool = False) -> dict:
    cer_scores = []
    exact_matches = 0
    errors = 0

    desc = "평가 중 (direct)" if use_direct else f"평가 중 ({ocr_type})"
    for rec in tqdm(records, desc=desc, unit="건"):
        ref = rec["conversations"][1]["value"]
        if use_direct:
            pred = run_ocr_direct(model, tokenizer, rec["image"])
        else:
            pred = run_ocr_chat(model, tokenizer, rec["image"], ocr_type)
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

    # 2. Fine-tuned 모델 평가 (학습 시와 동일한 images 텐서 방식)
    print("\n[2/2] Fine-tuned GOT-OCR 2.0 평가 (direct 방식)...")
    ft_model, ft_tok = load_base_model(lora_path=LORA_PATH)
    r = evaluate(ft_model, ft_tok, sample, use_direct=True)
    results["finetuned_direct"] = r
    print(f"  [direct] CER: {r['mean_cer']:.4f} | EM: {r['exact_match_rate']:.4f} | n={r['sample_count']}")

    # 결과 저장
    save_result(OUTPUT_DIR / "evaluation_comparison.json", results)

    # 요약 출력
    base_ocr = results["base_ocr"]
    ft = results["finetuned_direct"]
    cer_diff = base_ocr["mean_cer"] - ft["mean_cer"]
    print("\n=== 결과 요약 ===")
    print(f"  Base (ocr)      CER: {base_ocr['mean_cer']:.4f} | EM: {base_ocr['exact_match_rate']:.4f}")
    print(f"  Base (format)   CER: {results['base_format']['mean_cer']:.4f} | EM: {results['base_format']['exact_match_rate']:.4f}")
    print(f"  Finetuned       CER: {ft['mean_cer']:.4f} | EM: {ft['exact_match_rate']:.4f}")
    print(f"  CER 개선 (vs base ocr): {cer_diff:+.4f} ({'개선' if cer_diff > 0 else '악화'})")

if __name__ == "__main__":
    main()
