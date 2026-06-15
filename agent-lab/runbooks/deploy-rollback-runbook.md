# Runbook: Deploy và Rollback PaddleOCR GPU trên Windows Server

Runbook này hướng dẫn các bước kiểm tra phần cứng, thiết lập môi trường, triển khai bộ phát hiện PaddleOCR chạy trên GPU NVIDIA RTX 5060 Ti (kiến trúc Blackwell `sm_120`), sử dụng CUDA 12.8 và PyTorch `cu128`, cũng như các bước rollback về CPU nếu xảy ra sự cố.

---

## 1. Audit Phần Cứng và Phần Mềm trên Server (Pre-requisites)

Trước khi tiến hành deploy, operator cần kiểm tra cấu hình phần cứng và phần mềm của Windows Server để đảm bảo các ràng buộc được đáp ứng.

Chạy các lệnh PowerShell sau để kiểm tra:

```powershell
# 1. Kiểm tra card đồ họa NVIDIA và Driver Version
nvidia-smi

# Ràng buộc: Card đồ họa là RTX 5060 Ti 16GB. Driver version hỗ trợ CUDA 12.8+.

# 2. Kiểm tra CUDA Toolkit global version
nvcc --version

# Ràng buộc: CUDA Toolkit là bản 12.8. (Không chấp nhận CUDA 12.9 hoặc cũ hơn).

# 3. Kiểm tra phiên bản Python hệ thống (yêu cầu Python 3.11 x64)
python --version
```

---

## 2. Thiết lập Môi trường ảo GPU và Tải mô hình

Triển khai môi trường ảo độc lập `.venv-gpu` để tránh gây ảnh hưởng tới môi trường CPU hiện có.

Chạy kịch bản setup tự động trong PowerShell:

```powershell
# Chạy script setup môi trường GPU
.\scripts\setup_windows_gpu.ps1
```

Script sẽ tự động:
1. Tạo môi trường ảo tại `.venv-gpu`.
2. Cập nhật `pip`, `setuptools`, `wheel`.
3. Cài đặt các package chung từ `requirements-base.txt`.
4. Cài đặt PyTorch `cu128` từ Index PyTorch chính thức.
5. Cài đặt `onnxruntime-gpu==1.22.0`.
6. Thực hiện smoke test DLL và in phiên bản.

**Tải mô hình Detector ONNX:**
Mô hình `model.onnx` của PP-OCRv5 detector phải được tải sẵn và đặt tại:
`models/onnx/PP-OCRv5_server_det/model.onnx`
SHA-256 Checksum yêu cầu: `0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad`

---

## 3. Cấu hình Môi trường GPU (Strict Mode)

Tạo file cấu hình môi trường `.env` cho GPU mode:

```dotenv
PORT=8093
OCR_DEVICE=gpu
OCR_GPU_REQUIRED=true
OCR_GPU_INDEX=0
OCR_DETECTOR_BACKEND=onnxruntime
OCR_DETECTOR_ONNX_MODEL=models/onnx/PP-OCRv5_server_det/model.onnx
OCR_ORT_DISABLE_CPU_FALLBACK=true

# Giới hạn số luồng tính toán toán học để tránh tranh chấp CPU
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
VECLIB_MAXIMUM_THREADS=1
NUMEXPR_NUM_THREADS=1

# Tắt MKLDNN của PaddlePaddle (để tránh lỗi C++ khi chạy CPU fallback)
FLAGS_use_mkldnn=0
FLAGS_use_onednn=0
```

---

## 4. Chạy Service GPU trên Port Tạm và Smoke Test

Khởi chạy ứng dụng bằng môi trường ảo GPU mới trên cổng tạm `8093` để kiểm tra trước khi đổi routing:

```powershell
# Khởi chạy server trên cổng tạm 8093
.\.venv-gpu\Scripts\python.exe -u app_backend.py > server_gpu_run.log 2>&1
```

**Smoke Test và Kiểm tra Readiness:**
Gửi yêu cầu GET đến endpoint `/health` để xác minh trạng thái nạp GPU và tắt CPU fallback:

```powershell
curl http://localhost:8093/health
```

Bản tin phản hồi thành công (đầy đủ thông tin GPU):
```json
{
  "status": "ready",
  "engine": "extraction_ocr_engine",
  "requested_device": "gpu",
  "gpu_required": true,
  "detector": {
    "framework": "onnxruntime",
    "device": "gpu",
    "provider": "CUDAExecutionProvider",
    "cpu_fallback": false,
    "verified": true
  },
  "recognizer": {
    "framework": "vietocr/pytorch",
    "device": "cuda:0",
    "verified": true
  },
  "gpu_detail": {
    "index": 0,
    "name": "NVIDIA GeForce RTX 5060 Ti"
  }
}
```

*Lưu ý:* Nếu server khởi chạy thất bại hoặc báo lỗi ở console, kiểm tra file `server_gpu_run.log` ngay. Do strict validation được bật, nếu CUDA EP không hoạt động, server sẽ báo lỗi và dừng tiến trình lập tức.

**Chạy Benchmark kiểm chứng:**
```powershell
# Chạy benchmark reproducible trên cổng tạm
$env:PYTHONPATH="E:\project\project-plugin-chat-bot\project-ocr-5-6-2026"; .\.venv-gpu\Scripts\python.exe tools/run_reproducible_benchmark.py --server-url http://localhost:8093 --output-dir benchmark/gpu_migration_runs/deploy_test
```

---

## 5. Chuyển đổi Service Binding (Promotion to Production)

Sau khi cổng tạm `8093` hoạt động ổn định và vượt qua benchmark, tiến hành cập nhật cấu hình reverse proxy (ví dụ Nginx hoặc IIS) để trỏ bind sang cổng GPU mới hoặc cập nhật file `.env` sản xuất về port `8091` và khởi chạy lại.

Nếu dùng cấu hình cập nhật trực tiếp:
1. Dừng service CPU cũ chạy trên port `8091`.
2. Đổi file `.env` của GPU port về `8091`.
3. Khởi chạy server GPU:
   ```powershell
   .\.venv-gpu\Scripts\python.exe -u app_backend.py > server_production.log 2>&1
   ```
4. Gửi curl tới `http://localhost:8091/health` để kiểm tra readiness.

---

## 6. Kịch bản Rollback về CPU khi xảy ra sự cố

Nếu sau khi triển khai lên GPU gặp lỗi rò rỉ bộ nhớ GPU (VRAM OOM), lỗi kernel CUDA, hoặc độ chính xác bị regression nghiêm trọng:

1. **Dừng ngay tiến trình GPU đang chạy:**
   ```powershell
   # Tìm và kill tiến trình Python đang chạy trên venv-gpu
   Get-Process | Where-Object {$_.Path -like "*venv-gpu*"} | Stop-Process -Force
   ```
2. **Khôi phục cấu hình CPU cũ:**
   Đảm bảo file `.env` được khôi phục các biến gốc:
   ```dotenv
   PORT=8091
   OCR_DEVICE=auto
   FLAGS_use_mkldnn=1
   FLAGS_use_onednn=1
   ```
3. **Khởi chạy lại bằng môi trường CPU ảo cũ (`.venv`):**
   ```powershell
   .\.venv\Scripts\python.exe -u app_backend.py > server_run.log 2>&1
   ```
4. **Kiểm tra Readiness:**
   ```powershell
   curl http://localhost:8091/health
   ```
5. **Thu thập tài liệu và log lỗi:**
   Lưu lại các file log sau để đội phát triển phân tích:
   - `server_gpu_run.log`
   - `server_production.log`
   - Dump lỗi CUDA (nếu có)
