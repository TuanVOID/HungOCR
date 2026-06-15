import os
import sys
import time
import json
import csv
import subprocess
import hashlib
import requests
import numpy as np
from pathlib import Path
from datetime import datetime

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.ocr_benchmark_common import make_session, score_text_pair, normalize_for_scoring, call_local_ocr

def get_git_commit():
    try:
        res = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"

def get_model_checksum(file_path):
    if not os.path.exists(file_path):
        return "not_found"
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256.update(byte_block)
    return sha256.hexdigest()

def get_package_versions():
    versions = {}
    packages = ['torch', 'torchvision', 'onnxruntime', 'onnxruntime-gpu', 'paddlepaddle', 'vietocr']
    for pkg in packages:
        try:
            import importlib
            mod = importlib.import_module(pkg)
            versions[pkg] = getattr(mod, '__version__', 'available')
        except ImportError:
            versions[pkg] = "not_installed"
    return versions

def run_benchmark(server_url, manifest_file, output_dir, iterations=3, warmup_count=5):
    session = make_session()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Fetch Health Details
    print("Fetching health status from server...")
    try:
        health_res = session.get(f"{server_url.rstrip('/')}/health", timeout=20)
        health_data = health_res.json()
    except Exception as e:
        print(f"Error fetching health details: {e}")
        health_data = {"status": "unknown", "error": str(e)}

    # 2. Load manifest
    print(f"Loading manifest from: {manifest_file}")
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    samples = manifest.get("samples", [])
    if not samples:
        print("No samples found in manifest.")
        return
        
    print(f"Loaded {len(samples)} samples from manifest.")

    # 3. Warm-up Phase
    print(f"\n--- Warm-up Phase: Sending {warmup_count} requests ---")
    warmup_latencies = []
    warmup_sample = samples[0]
    warmup_img_path = Path(warmup_sample["image_path"])
    
    if not warmup_img_path.exists():
        # Fallback to local search if path absolute to developer machine
        local_img_path = Path(__file__).resolve().parents[1] / "benchmark" / "vietnamese_ocr_overall_runs" / "20260605-143945" / "images" / warmup_img_path.name
        if local_img_path.exists():
            warmup_img_path = local_img_path
            
    for i in range(warmup_count):
        with open(warmup_img_path, "rb") as img_file:
            files = [("files", (warmup_img_path.name, img_file, "image/png"))]
            t0 = time.time()
            res = session.post(f"{server_url.rstrip('/')}/ocr", files=files, timeout=180)
            latency = time.time() - t0
            warmup_latencies.append(latency)
            print(f"Warm-up {i+1}/{warmup_count}: Latency = {latency:.4f} seconds (Status: {res.status_code})")

    cold_start = warmup_latencies[0]
    warm_latencies = warmup_latencies[1:]
    avg_warm_latency = np.mean(warm_latencies) if warm_latencies else cold_start
    print(f"Cold Start Latency: {cold_start:.4f}s, Avg Warm-up Latency (excluding cold start): {avg_warm_latency:.4f}s")

    # 4. Benchmark Phase (Iterations)
    print(f"\n--- Benchmark Phase: Running {iterations} iterations over {len(samples)} images ---")
    all_runs = []
    
    for iteration in range(1, iterations + 1):
        print(f"\nStarting Iteration {iteration}/{iterations}...")
        iteration_latencies = []
        
        for idx, sample in enumerate(samples):
            img_path = Path(sample["image_path"])
            if not img_path.exists():
                img_path = Path(__file__).resolve().parents[1] / "benchmark" / "vietnamese_ocr_overall_runs" / "20260605-143945" / "images" / img_path.name
                
            t0 = time.time()
            ocr_text = ""
            try:
                ocr_text = call_local_ocr(session, server_url, img_path)
            except Exception as e:
                print(f"  Error calling OCR for {img_path.name}: {e}")
            latency = time.time() - t0
                
            iteration_latencies.append(latency)
            
            # Score accuracy
            accuracy, cer, distance, src_len, ocr_len = score_text_pair(sample["source_text"], ocr_text)
            
            all_runs.append({
                "iteration": iteration,
                "sample_id": sample["sample_id"],
                "kind": sample["kind"],
                "transform": sample["transform"],
                "latency": latency,
                "accuracy": accuracy,
                "cer": cer,
                "source_length": src_len,
                "ocr_length": ocr_len
            })
            
            print(f"  [{iteration}/{idx+1}] Sample: {sample['sample_id']}, Latency: {latency:.4f}s, Accuracy: {accuracy*100:.2f}%")

    # 5. Compute Stats
    latencies = [run["latency"] for run in all_runs]
    accuracies = [run["accuracy"] for run in all_runs]
    
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    mean_latency = np.mean(latencies)
    min_latency = np.min(latencies)
    max_latency = np.max(latencies)
    throughput = 1.0 / mean_latency if mean_latency > 0 else 0
    mean_accuracy = np.mean(accuracies)

    git_commit = get_git_commit()
    onnx_checksum = get_model_checksum("models/onnx/PP-OCRv5_server_det/model.onnx")
    packages = get_package_versions()

    # 6. Save Reports
    print("\n--- Saving Benchmark Reports ---")
    
    # Save JSON Report
    report_data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit,
        "onnx_model_checksum": onnx_checksum,
        "packages": packages,
        "health_status": health_data,
        "metrics": {
            "cold_start_latency": cold_start,
            "mean_latency": mean_latency,
            "min_latency": min_latency,
            "max_latency": max_latency,
            "p50_latency": p50,
            "p95_latency": p95,
            "throughput_req_per_sec": throughput,
            "mean_accuracy": mean_accuracy,
        },
        "runs": all_runs
    }
    
    json_path = output_path / "benchmark_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
        
    # Save CSV Report
    csv_path = output_path / "benchmark_report.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Iteration", "Sample ID", "Kind", "Transform", "Latency (s)", "Accuracy", "CER", "Source Len", "OCR Len"])
        for run in all_runs:
            writer.writerow([
                run["iteration"], run["sample_id"], run["kind"], run["transform"],
                f"{run['latency']:.4f}", f"{run['accuracy']:.4f}", f"{run['cer']:.4f}",
                run["source_length"], run["ocr_length"]
            ])

    # Save Markdown Report
    md_path = output_path / "benchmark_report.md"
    md_lines = [
        "# Reproducible OCR Benchmark Report",
        "",
        f"- Generated at: `{report_data['generated_at']}`",
        f"- Git Commit Hash: `{git_commit}`",
        f"- ONNX Model Checksum: `{onnx_checksum}`",
        "",
        "## Device / Health Status",
        "```json",
        json.dumps(health_data, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Performance Metrics Summary",
        "",
        f"- **Cold Start Latency**: `{cold_start:.4f} seconds`",
        f"- **Mean Latency (warm)**: `{mean_latency:.4f} seconds`",
        f"- **Min Latency**: `{min_latency:.4f} seconds`",
        f"- **Max Latency**: `{max_latency:.4f} seconds`",
        f"- **p50 Latency**: `{p50:.4f} seconds`",
        f"- **p95 Latency**: `{p95:.4f} seconds`",
        f"- **Throughput**: `{throughput:.2f} requests/second`",
        f"- **Mean Accuracy**: `{mean_accuracy * 100:.2f}%`",
        "",
        "## Python Package Versions",
        "| Package | Version |",
        "| --- | --- |"
    ]
    for pkg, ver in packages.items():
        md_lines.append(f"| {pkg} | {ver} |")
        
    md_lines += [
        "",
        "## Detailed Runs",
        "",
        "| Iteration | Sample ID | Kind | Transform | Latency (s) | Accuracy |",
        "| --- | --- | --- | --- | ---: | ---: |"
    ]
    for run in all_runs:
        md_lines.append(
            f"| {run['iteration']} | `{run['sample_id']}` | {run['kind']} | {run['transform']} | "
            f"{run['latency']:.4f} | {run['accuracy'] * 100:.2f}% |"
        )
        
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    
    print(f"JSON report saved to: {json_path}")
    print(f"CSV report saved to:  {csv_path}")
    print(f"MD report saved to:   {md_path}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run reproducible OCR benchmark.")
    parser.add_argument("--server-url", default="http://localhost:8091", help="OCR server URL")
    parser.add_argument("--manifest-file", default="benchmark/vietnamese_ocr_overall_runs/20260605-143945/manifest.json", help="Path to manifest file")
    parser.add_argument("--output-dir", required=True, help="Directory to save reports")
    parser.add_argument("--iterations", type=int, default=3, help="Number of benchmark iterations")
    parser.add_argument("--warmup-count", type=int, default=5, help="Number of warmup requests")
    
    args = parser.parse_args()
    run_benchmark(
        server_url=args.server_url,
        manifest_file=args.manifest_file,
        output_dir=args.output_dir,
        iterations=args.iterations,
        warmup_count=args.warmup_count
    )

if __name__ == "__main__":
    main()
