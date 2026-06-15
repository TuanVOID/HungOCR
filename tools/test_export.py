import os
import paddle2onnx
from pathlib import Path

model_path = "C:/Users/admin/.paddlex/official_models/PP-OCRv5_server_det/inference.json"
params_path = "C:/Users/admin/.paddlex/official_models/PP-OCRv5_server_det/inference.pdiparams"

onnx_dir = Path("E:/project/project-plugin-chat-bot/project-ocr-5-6-2026/models/onnx/PP-OCRv5_server_det")
onnx_dir.mkdir(parents=True, exist_ok=True)
save_file = str(onnx_dir / "model.onnx")

print("Starting export via paddle2onnx.export API...")
try:
    result = paddle2onnx.export(
        model_filename=model_path,
        params_filename=params_path,
        save_file=save_file,
        opset_version=11,
        enable_onnx_checker=True
    )
    print("Export result:", result)
except Exception as e:
    print("Export failed with exception:", e)
