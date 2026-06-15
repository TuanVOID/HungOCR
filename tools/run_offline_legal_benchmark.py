import os
import sys
import json
import time
import requests
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import re
import unicodedata
from rapidfuzz.distance import Levenshtein
from tools.ocr_benchmark_common import make_session, call_local_ocr

def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()
    return text

def normalize_for_scoring(text: str) -> str:
    text = normalize_whitespace(text)
    if not text:
        return ""
    text = text.lower()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s*([/.,;:()\[\]{}\-])\s*", r"\1", text)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()
    return text

def score_text_pair(source_text: str, ocr_text: str) -> tuple[float, float, int, int, int]:
    source_norm = normalize_for_scoring(source_text)
    ocr_norm = normalize_for_scoring(ocr_text)

    if not source_norm and not ocr_norm:
        return 1.0, 0.0, 0, 0, 0

    distance = Levenshtein.distance(source_norm, ocr_norm)
    denominator = max(len(source_norm), len(ocr_norm), 1)
    accuracy = max(0.0, 1.0 - (distance / denominator))
    cer = distance / max(len(source_norm), 1)
    return accuracy, cer, distance, len(source_norm), len(ocr_norm)

def main():
    server_url = "http://localhost:8093"
    
    # Paths
    run_dir = Path("benchmark/thuvienphapluat_legal_ocr_10docs_runs/20260608-162712")
    manifest_file = run_dir / "manifest.json"
    output_dir = Path("benchmark/thuvienphapluat_legal_ocr_10docs_runs/20260615-gpu-run")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading manifest from: {manifest_file}")
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    samples = manifest.get("samples", [])
    print(f"Loaded {len(samples)} samples.")
    
    session = make_session()
    
    # Warm up
    print("Warming up...")
    warmup_img = Path(samples[0]["image_path"])
    # Resolve relative path if needed
    if not warmup_img.exists():
        warmup_img = run_dir / "images" / warmup_img.name
        
    for i in range(2):
        try:
            call_local_ocr(session, server_url, warmup_img)
        except Exception as e:
            print(f"Warmup error: {e}")
            
    print("Starting offline benchmark...")
    results = []
    
    for idx, sample in enumerate(samples):
        img_path = Path(sample["image_path"])
        if not img_path.exists():
            img_path = run_dir / "images" / img_path.name
            
        print(f"[{idx+1}/{len(samples)}] OCR-ing {img_path.name}...")
        t0 = time.time()
        ocr_text = ""
        try:
            ocr_text = call_local_ocr(session, server_url, img_path)
        except Exception as e:
            print(f"Error processing {img_path.name}: {e}")
            
        latency = time.time() - t0
        accuracy, cer, distance, src_len, ocr_len = score_text_pair(sample["source_text"], ocr_text)
        
        results.append({
            "sample_id": sample.get("sample_id", f"sample-{idx}"),
            "document_title": sample.get("document_title", ""),
            "page_index": sample.get("page_index", 0),
            "latency": latency,
            "accuracy": accuracy,
            "cer": cer,
            "edit_distance": distance,
            "source_length": src_len,
            "ocr_length": ocr_len
        })
        
        print(f"   Accuracy: {accuracy*100:.2f}%, Latency: {latency:.2f}s")
        
    # Stats
    total_source = sum(r["source_length"] for r in results)
    total_distance = sum(r["edit_distance"] for r in results)
    weighted_acc = 1.0 if total_source == 0 else max(0.0, 1.0 - (total_distance / total_source))
    mean_acc = sum(r["accuracy"] for r in results) / len(results) if results else 0.0
    mean_lat = sum(r["latency"] for r in results) / len(results) if results else 0.0
    
    print("\n=== OFFLINE BENCHMARK RESULTS ===")
    print(f"Total Samples: {len(results)}")
    print(f"Weighted Accuracy: {weighted_acc*100:.2f}%")
    print(f"Mean Accuracy: {mean_acc*100:.2f}%")
    print(f"Mean Latency: {mean_lat:.2f}s")
    
    # Save report JSON
    report_json_path = output_dir / "report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "weighted_accuracy": weighted_acc,
            "mean_accuracy": mean_acc,
            "mean_latency": mean_lat,
            "samples": results
        }, f, ensure_ascii=False, indent=2)
        
    print(f"Saved JSON report to: {report_json_path}")

if __name__ == "__main__":
    main()
