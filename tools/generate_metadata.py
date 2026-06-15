import hashlib
import json
import onnx
from pathlib import Path

model_path = Path("E:/project/project-plugin-chat-bot/project-ocr-5-6-2026/models/onnx/PP-OCRv5_server_det/model.onnx")

print("Loading ONNX model to extract metadata...")
model = onnx.load(str(model_path))

# 1. Tính SHA-256
sha256_hash = hashlib.sha256()
with open(model_path, "rb") as f:
    for byte_block in iter(lambda: f.read(8192), b""):
        sha256_hash.update(byte_block)
sha256_val = sha256_hash.hexdigest()
print("SHA-256:", sha256_val)

# 2. Lấy opset version
opset_version = None
for opset in model.opset_import:
    if opset.domain == "" or opset.domain == "ai.onnx":
        opset_version = opset.version
        break

# 3. Lấy thông tin input
inputs = []
for inp in model.graph.input:
    shape = []
    dim_info = inp.type.tensor_type.shape
    for dim in dim_info.dim:
        if dim.HasField("dim_value"):
            shape.append(dim.dim_value)
        elif dim.HasField("dim_param"):
            shape.append(dim.dim_param)
        else:
            shape.append("?")
    inputs.append({
        "name": inp.name,
        "type": onnx.TensorProto.DataType.Name(inp.type.tensor_type.elem_type),
        "shape": shape
    })

# 4. Lấy thông tin output
outputs = []
for out in model.graph.output:
    shape = []
    dim_info = out.type.tensor_type.shape
    for dim in dim_info.dim:
        if dim.HasField("dim_value"):
            shape.append(dim.dim_value)
        elif dim.HasField("dim_param"):
            shape.append(dim.dim_param)
        else:
            shape.append("?")
    outputs.append({
        "name": out.name,
        "type": onnx.TensorProto.DataType.Name(out.type.tensor_type.elem_type),
        "shape": shape
    })

metadata = {
    "model_name": "PP-OCRv5_server_det",
    "description": "PP-OCRv5 server text detection model exported to ONNX.",
    "source_url": "https://huggingface.co/breezedeus/cnstd-ppocr-ch_PP-OCRv5_det_server",
    "sha256": sha256_val,
    "opset": opset_version,
    "inputs": inputs,
    "outputs": outputs
}

metadata_path = model_path.parent / "model.metadata.json"
with open(metadata_path, "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)
    
print(f"Metadata written successfully to {metadata_path}")
print(json.dumps(metadata, indent=2))
