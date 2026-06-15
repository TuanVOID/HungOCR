import os
import sys
from pathlib import Path

site_packages = Path("E:/project/project-plugin-chat-bot/project-ocr-5-6-2026/.venv-export/lib/site-packages")
paddle_dir = site_packages / "paddle"

# Thêm tất cả các thư mục chứa file .dll của paddle
added = set()
for p in paddle_dir.rglob("*.dll"):
    dir_path = str(p.parent)
    if dir_path not in added:
        print("Adding DLL directory:", dir_path)
        try:
            os.add_dll_directory(dir_path)
            added.add(dir_path)
        except Exception as err:
            print(f"Failed to add {dir_path}: {err}")

try:
    import paddle
    import paddle2onnx
    print("Success! Import paddle2onnx successfully after adding DLL paths.")
except Exception as e:
    print("Import still failed:")
    import traceback
    traceback.print_exc()
