import os
import requests
from pathlib import Path

ONNX_URL = "https://huggingface.co/breezedeus/cnstd-ppocr-ch_PP-OCRv5_det_server/resolve/main/ch_PP-OCRv5_det_server_infer.onnx"
DEST_DIR = Path("E:/project/project-plugin-chat-bot/project-ocr-5-6-2026/models/onnx/PP-OCRv5_server_det")
DEST_DIR.mkdir(parents=True, exist_ok=True)

onnx_path = DEST_DIR / "model.onnx"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print(f"Downloading pre-exported ONNX model from {ONNX_URL}...")
response = requests.get(ONNX_URL, headers=headers, stream=True)
response.raise_for_status()

with open(onnx_path, "wb") as f:
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)
            
print(f"Model downloaded successfully and saved to {onnx_path}.")
