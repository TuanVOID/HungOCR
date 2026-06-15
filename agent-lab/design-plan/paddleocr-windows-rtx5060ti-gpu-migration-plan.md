# Ke hoach chuyen PaddleOCR sang GPU tren Windows Server RTX 5060 Ti 16 GB

## 1. Muc tieu

Chuyen dich vu trong `C:\Indti\project-ocr\PaddleOCR` sang dung GPU NVIDIA RTX 5060 Ti 16 GB tren Windows Server, voi cac dieu kien bat buoc:

- PP-OCRv5 detector chay bang ONNX Runtime CUDA Execution Provider tren CUDA 12.8.
- VietOCR recognizer chay bang PyTorch CUDA.
- Neu cau hinh production yeu cau GPU ma mot trong hai framework khong dung duoc GPU, backend phai dung khoi dong va bao loi ro rang; khong duoc am tham roi ve CPU.
- OCR phai xu ly thanh cong bo test dai dien, khong co loi CUDA, DLL, `sm_120`, het VRAM hoac ket qua rong bat thuong.
- Ket qua OCR tren GPU khong duoc suy giam dang ke so voi CPU.
- Benchmark OCR-only tren GPU phai nhanh hon CPU tren cung server va cung bo du lieu.
- Co rollback ve moi truong CPU cu ma khong can cai lai server.

## 2. Hien trang va bang chung trong code

Code hien tai da co nen tang chon thiet bi:

- `PaddleOCR/app_backend.py::detect_ocr_devices()` nhan `OCR_DEVICE=auto|gpu|cpu`.
- Paddle detector hien tai nhan `device=paddle_device`; implementation moi se thay backend detector bang ONNX Runtime CUDA.
- VietOCR nhan `config['device']=torch_device`.
- `.env.example` da co `OCR_DEVICE=auto`.

Nhung chua du an toan cho production GPU:

- `requirements.txt` dang cai `paddlepaddle==3.2.0`, day la ban CPU va khong the tang toc detector tren GPU.
- `torch` va `torchvision` khong pin ban CUDA, nen `pip` co the cai wheel CPU.
- Khi `OCR_DEVICE=gpu`, code hien tai tra ngay `("gpu", "cuda")` ma khong kiem tra framework co thuc su truy cap GPU hay khong.
- `/health` chi tra `status=ready`, khong cho biet detector va recognizer dang chay tren CPU hay GPU.
- Detector va recognizer nam trong cung mot process. Tren Windows can nap dung DLL CUDA/cuDNN cho ONNX Runtime va PyTorch.
- `MODEL_INFERENCE_LOCK` dang serialize detector va recognizer. Dot dau giu nguyen de uu tien dung va on dinh; chi toi uu concurrency sau khi co benchmark.

## 3. Quyet dinh ky thuat ban dau

### 3.1 Nen tang

- Uu tien Windows Server native, Python 3.11 x64.
- Tao virtualenv GPU moi, khong sua truc tiep `.venv` CPU dang chay.
- Giu virtualenv CPU cu de rollback.
- Chua bat TensorRT, HPI hoac mixed precision trong dot dau.

### 3.2 CUDA cho RTX 5060 Ti

Rang buoc cua dot trien khai nay la giu CUDA Toolkit global 12.8, khong cai va khong dung wheel `cu129`.

RTX 5060 Ti thuoc Blackwell, compute capability `sm_120`. PyTorch co wheel `cu128` ho tro Blackwell. ONNX Runtime GPU tu dong 1.19 tro len dung CUDA 12.x/cuDNN 9 va tai lieu ONNX Runtime neu ro build CUDA 12.x tuong thich cac CUDA 12.x nho co CUDA minor-version compatibility.

Khong dung PaddlePaddle GPU wheel lam runtime detector trong phuong an CUDA 12.8 native Windows, vi:

- Index Paddle `cu128` hien chi liet ke wheel Linux 3.2.0, khong co wheel Windows tuong ung.
- Paddle build cu khong chua `sm_120` co the cai thanh cong nhung loi `Unsupported GPU architecture` khi inference.
- Dung wheel `cu126` hoac CPU wheel roi dat `device=gpu` khong dap ung yeu cau chay dung va fail-fast.

Vi vay model text detection PP-OCRv5 van duoc giu, nhung duoc export sang ONNX va chay bang `CUDAExecutionProvider`. VietOCR chay bang PyTorch `cu128`. PaddlePaddle CPU chi duoc dung trong moi truong export model neu can, khong nam tren duong inference production.

Truoc khi cai Python package can:

1. Kiem tra `nvidia-smi`, khong chi dua vao `nvcc --version`.
2. Xac nhan NVIDIA driver ho tro RTX 5060 Ti va CUDA 12.8.
3. Xac nhan `nvcc --version` la CUDA Toolkit 12.8 theo dung rang buoc server.
4. Xac nhan cuDNN 9/DLL can thiet co the duoc nap tu PyTorch cu128 hoac bo CUDA/cuDNN global.
5. Khoi dong lai server neu driver hoac bien `PATH` vua thay doi.

Luu y: `CUDA Version` cua `nvidia-smi` la muc CUDA toi da driver ho tro; `nvcc --version` la toolkit dang duoc chon trong `PATH`. Toolkit production phai la 12.8; driver moi hon van duoc chap nhan neu tuong thich nguoc.

### 3.3 Bo version ung vien

Bo version dau tien de test tren Python 3.11:

- `onnxruntime-gpu==1.22.0` cho detector CUDA 12.x/cuDNN 9.
- `torch==2.10.0` va `torchvision==0.25.0` tu index chinh thuc `cu128` cua PyTorch.
- `vietocr==0.3.13` hoac dung dung version da test thanh cong, sau do pin lai.
- `paddle2onnx` va `paddlepaddle==3.2.0` chi trong moi truong export model rieng neu qua trinh export can.

PyTorch phai duoc import truoc khi tao ONNX Runtime session, hoac goi `onnxruntime.preload_dlls()`, de ONNX Runtime nap dung CUDA/cuDNN DLL. Neu bo version ung vien khong tuong thich VietOCR hoac model ONNX, chi thay doi theo mot ma tran version co kiem soat va luu ket qua; khong dung package `latest` khong pin trong production.

## 4. Pham vi thay doi du kien

### 4.1 Dependency va script cai dat

Tach dependency ung dung khoi inference engine de `pip install -r requirements.txt` khong vo tinh ghi de GPU wheel bang CPU wheel:

- Tao requirements chung khong chua inference engine co the ghi de wheel GPU.
- Tao script `scripts/setup_windows_gpu.ps1` cai dependency chung, ONNX Runtime GPU va PyTorch cu128 tu official index.
- Tao script `scripts/setup_windows_cpu.ps1` hoac giu huong dan CPU rieng.
- Tao script `scripts/export_detector_onnx.ps1` chay trong virtualenv export rieng.
- Sau khi test dat, xuat file lock co version va hash/package source thuc te.
- Script phai dung duong dan Python trong virtualenv, khong dung `pip` global.

Lenh cai dat ung vien:

```powershell
py -3.11 -m venv .venv-gpu
.\.venv-gpu\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv-gpu\Scripts\python.exe -m pip install -r requirements-base.txt
.\.venv-gpu\Scripts\python.exe -m pip uninstall -y onnxruntime onnxruntime-gpu torch torchvision
.\.venv-gpu\Scripts\python.exe -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv-gpu\Scripts\python.exe -m pip install onnxruntime-gpu==1.22.0
```

Khong chay lai requirements cu sau cac lenh tren neu requirements cu van chua package CPU.

### 4.2 Phat hien va bat buoc dung GPU

Refactor `detect_ocr_devices()` thanh mot cau hinh runtime co du thong tin:

- `requested_device`: `auto`, `gpu`, `cpu`.
- `gpu_index`: mac dinh `0`.
- `detector_provider`: `CUDAExecutionProvider` hoac `CPUExecutionProvider`.
- `torch_device`: `cuda:0` hoac `cpu`.
- Ten GPU, version driver/framework/CUDA runtime va ket qua smoke test.

Them bien moi truong:

```dotenv
OCR_DEVICE=gpu
OCR_GPU_REQUIRED=true
OCR_GPU_INDEX=0
OCR_DETECTOR_BACKEND=onnxruntime
OCR_DETECTOR_ONNX_MODEL=models/onnx/PP-OCRv5_server_det/model.onnx
OCR_ORT_DISABLE_CPU_FALLBACK=true
```

Quy tac:

- `OCR_DEVICE=cpu`: chay CPU co chu dich.
- `OCR_DEVICE=auto`: uu tien GPU khi ca ONNX Runtime CUDA va Torch dat kiem tra; cho phep CPU tren may khong co NVIDIA neu `OCR_GPU_REQUIRED=false`.
- `OCR_DEVICE=gpu` hoac `OCR_GPU_REQUIRED=true`: bat buoc detector ONNX va recognizer Torch dung GPU. Thieu mot ben la startup error.
- Gia tri bien moi truong khong hop le phai startup error, khong tu sua ve `auto`.

Kiem tra ONNX Runtime detector toi thieu:

- Import PyTorch/preload CUDA DLL truoc khi tao ONNX Runtime session.
- `CUDAExecutionProvider` nam trong `onnxruntime.get_available_providers()`.
- Tao session voi `CUDAExecutionProvider`, dung `device_id=0`.
- Dat `session.disable_cpu_ep_fallback=1` khi `OCR_ORT_DISABLE_CPU_FALLBACK=true` de operator khong duoc am tham roi ve CPU.
- `session.get_providers()[0]` la `CUDAExecutionProvider`.
- Chay model detector ONNX that tren anh smoke thanh cong.
- Bat verbose/profiling trong integration test de audit node placement neu can.

Kiem tra PyTorch toi thieu:

- Import thanh cong.
- `torch.version.cuda` khong rong.
- `torch.cuda.is_available()` la `True`.
- `torch.cuda.device_count() > GPU_INDEX`.
- Ten device dung la RTX 5060 Ti.
- Chay tensor/matmul tren `cuda:0`, goi `torch.cuda.synchronize()` thanh cong.
- Kiem tra build co ho tro `sm_120`, khong co canh bao `no kernel image is available`.

### 4.3 Startup va health check

Trinh tu startup du kien:

1. Doc cau hinh.
2. Kiem tra framework GPU va chay CUDA smoke operations.
3. Preload CUDA/cuDNN DLL, khoi tao ONNX Runtime detector bang `CUDAExecutionProvider`.
4. Khoi tao VietOCR tren `cuda:0`.
5. Chay mot anh smoke OCR nho co san trong repository.
6. Chi sau khi tat ca thanh cong moi tra `/health` la `ready`.

Mo rong `/health`, vi du:

```json
{
  "status": "ready",
  "requested_device": "gpu",
  "gpu_required": true,
  "detector": {"framework": "onnxruntime", "provider": "CUDAExecutionProvider", "device": "cuda:0", "verified": true, "cpu_fallback": false},
  "recognizer": {"framework": "torch", "device": "cuda:0", "verified": true},
  "gpu": {"index": 0, "name": "NVIDIA GeForce RTX 5060 Ti"}
}
```

Khong dua duong dan noi bo, credential hoac toan bo bien moi truong vao health response.

### 4.4 Cau hinh inference

- Khi chay GPU, detector khong dung MKLDNN/oneDNN; day la toi uu CPU, khong phai CUDA.
- Tiep tuc dung preprocessing va DB postprocessing cua PaddleOCR de giu semantics box detection, chi thay inference session bang ONNX Runtime.
- Giu `OCR_RECOGNITION_BATCH=true` de VietOCR nhan dang theo batch neu implementation ho tro.
- Giu mot instance detector va mot instance recognizer trong process.
- Giu `MODEL_INFERENCE_LOCK` trong dot dau de loai tru race condition va VRAM spike.
- Khong tang `OCR_MAX_WORKERS` voi ky vong tang GPU throughput truoc khi benchmark, vi inference hien bi serialize boi lock.
- Ghi log mot lan luc startup ve requested/actual device va version, khong log moi request.

## 5. Quy trinh trien khai

### Giai doan 0 - Snapshot va audit server

Chay va luu output vao artifact co timestamp:

```powershell
nvidia-smi
nvcc --version
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM, Status
where.exe python
py -0p
python --version
python -c "import platform; print(platform.architecture(), platform.machine())"
```

Dieu kien qua cong:

- `nvidia-smi` thay dung RTX 5060 Ti 16 GB va status binh thuong.
- Driver ho tro RTX 5060 Ti va CUDA 12.8.
- Python 3.11 x64 san sang.
- Co du dung luong dia cho virtualenv, wheel va model cache.

`nvcc --version` phai xac nhan CUDA Toolkit 12.8. Khong cai wheel `cu129` va khong nang toolkit sang 12.9 trong ke hoach nay.

### Giai doan 1 - Tao moi truong GPU sach

1. Ghi lai `pip freeze` cua moi truong CPU hien tai.
2. Tao `.venv-gpu` moi.
3. Cai dependencies theo dung thu tu trong muc 4.1.
4. Chay `pip check`.
5. Kiem tra ONNX Runtime co `CUDAExecutionProvider`.
6. Chay smoke test Torch CUDA.
7. Chay detector ONNX smoke test voi CPU fallback bi tat.
8. Xuat `pip freeze` va luu thong tin package source.

Khong copy nguyen `site-packages` tu `.venv` cu sang `.venv-gpu`.

### Giai doan 2 - Export model va kiem tra DLL tren Windows

Export dung model detector dang duoc production su dung sang ONNX trong moi truong rieng:

- Luu ten model, source URL/version, opset, input/output names va SHA-256 cua file ONNX.
- Chay cung mot tap anh qua Paddle CPU baseline va ONNX CPU, so sanh box count/toa do truoc khi dua len CUDA.
- Khong tu dong export lai model moi lan service khoi dong.

Trong virtualenv GPU, bat buoc test thu tu preload duoc ONNX Runtime khuyen nghi:

```powershell
.\.venv-gpu\Scripts\python.exe -c "import torch; import onnxruntime as ort; print(torch.__version__, torch.version.cuda, ort.__version__, ort.get_available_providers())"
```

Sau import, chay Torch tensor GPU va ONNX detector model trong cung process.

Dieu kien qua cong:

- Khong co `WinError 126`, `WinError 127`, DLL not found/procedure not found.
- Khong co crash process.
- Torch tinh toan tren GPU thanh cong.
- ONNX Runtime co `CUDAExecutionProvider`, tao session va detector inference thanh cong.
- Session duoc cau hinh khong CPU fallback; neu model co operator khong duoc CUDA EP ho tro thi test phai fail.

Chuan hoa thu tu import/preload som trong backend va them regression test. Neu van xung dot DLL, phuong an du phong la tach ONNX detector va VietOCR recognizer thanh hai process/service noi bo; khong chap nhan workaround chi hoat dong ngau nhien theo `PATH`.

### Giai doan 3 - Sua code va unit test

Thuc hien cac thay doi trong muc 4, sau do them test:

- `auto` + khong co NVIDIA -> CPU khi khong bat buoc GPU.
- `auto` + ca hai framework GPU hop le -> ONNX `CUDAExecutionProvider`, Torch `cuda:0`.
- `gpu` + ONNX Runtime chi co CPU provider -> startup fail.
- `gpu` + ONNX model co operator phai fallback CPU -> startup fail.
- `gpu` + Torch CPU wheel -> startup fail.
- GPU index khong ton tai -> startup fail.
- Gia tri `OCR_DEVICE` khong hop le -> startup fail.
- `/health` phan anh dung actual device.
- Health phai ghi `cpu_fallback=false` cho detector GPU.

Unit test dung monkeypatch/fake module, khong bat CI CPU phai co GPU. Integration test GPU duoc danh marker rieng va chi chay tren server GPU.

### Giai doan 4 - Integration test model that

Tren server GPU:

1. Bat backend o port tam, vi du `8093`.
2. Dat `OCR_DEVICE=gpu`, `OCR_GPU_REQUIRED=true`, `OCR_GPU_INDEX=0`.
3. Kiem tra startup log va `/health`.
4. Trong luc model da load, kiem tra process co VRAM allocation bang `nvidia-smi`.
5. OCR toi thieu cac nhom input:
   - Anh chu Viet ro.
   - Anh do phan giai lon hon 1500 px.
   - Anh xoay 90/180/270 do.
   - Anh chat luong thap.
   - PDF nhieu trang trong gioi han cho phep.
6. Kiem tra 100% request tra ve HTTP thanh cong, text khong rong voi input co chu va khong co loi CUDA trong log.

Can phan biet bang chung:

- VRAM tang chi cho thay model co nap vao GPU.
- Health + framework tensor test + actual model inference moi la bang chung GPU duoc dung dung.

### Giai doan 5 - Benchmark CPU va GPU

Chay hai lop benchmark:

1. So sanh cung code/cung package, chi doi `OCR_DEVICE=cpu` va `OCR_DEVICE=gpu`.
2. So sanh production CPU cu voi production GPU moi de do loi ich trien khai thuc te.

Bo test chinh:

- `tools/benchmark_vietnamese_ocr_overall.py`: 40 anh gom clean, xoay va low-quality.
- Bo 10 van ban phap luat da co de kiem tra tai lieu dai/dinh dang gan production.
- Them mot tap anh/PDF that tu production da an danh neu co.

Phuong phap do:

- Cache model truoc khi do warm latency.
- Warm-up it nhat 5 request khong tinh vao ket qua.
- Chay moi bo it nhat 3 lan, cung thu tu input.
- Do rieng cold startup, OCR request latency, tong wall-clock, p50, p95 va throughput.
- Ghi peak VRAM, GPU utilization, CPU utilization va RAM.
- Khong dua thoi gian goi Ollama/LLM qua mang vao benchmark OCR GPU chinh.
- Luu raw JSON/CSV, log version va hash commit de co the lap lai.

Dieu kien chap nhan:

- Ca detector va recognizer duoc health check xac nhan tren GPU.
- 40/40 anh benchmark va 10/10 tai lieu chay thanh cong.
- Weighted OCR accuracy tren GPU khong thap hon CPU qua 0.2 diem phan tram; moi regression lon tren tung mau phai duoc dieu tra.
- Khong co ket qua rong moi, crash, CUDA error, DLL error hoac OOM.
- Tong warm OCR time tren bo 40 anh giam it nhat 25% so voi CPU va p50 latency thap hon CPU.
- p95 khong xau hon CPU trong che do sequential; neu xau hon thi chua deploy cho den khi tim duoc nguyen nhan.

Muc tieu 25% la cong toi thieu de xac nhan GPU mang lai loi ich ro rang. Bao cao van phai ghi speedup thuc te, khong chi ghi pass/fail.

### Giai doan 6 - Rollout production

1. Giu service CPU cu va virtualenv cu nguyen trang.
2. Chay service GPU tren port tam `8093`.
3. Chay smoke va benchmark rut gon.
4. Chuyen reverse proxy/service binding sang service GPU trong cua so bao tri.
5. Theo doi toi thieu:
   - `/health` actual devices.
   - Error rate va request latency.
   - VRAM/RAM.
   - CUDA/DLL/OOM errors.
   - Hang doi request do `MODEL_INFERENCE_LOCK`.
6. Sau khi on dinh moi dung service CPU cu.

Rollback:

- Chuyen port/proxy ve service CPU cu.
- Khong sua package trong virtualenv CPU cu.
- Giu artifact log va input gay loi de dieu tra.
- `OCR_DEVICE=cpu` chi la fallback tam; production GPU khong duoc coi la dat neu phai dung fallback nay.

## 6. Toi uu sau khi ban GPU co ban da dat

Chi thuc hien sau khi correctness va benchmark co ban dat:

- Profile thoi gian detector va recognizer rieng de biet nut that.
- Dieu chinh batch size VietOCR theo VRAM 16 GB.
- Danh gia tach lock ONNX Runtime/Torch neu hai framework co the chay an toan ma khong tang OOM.
- Thu concurrency 2 va 4 voi gioi han queue/backpressure.
- Danh gia FP16/TensorRT/HPI trong mot nhanh benchmark rieng, co accuracy gate rieng.
- Khong bat toi uu chi vi GPU utilization thap; phai co benchmark end-to-end tot hon.

## 7. Rui ro va cach xu ly

- **PaddlePaddle khong co official Windows cu128 wheel phu hop `sm_120`:** khong dung Paddle GPU runtime; export PP-OCRv5 sang ONNX va dung ONNX Runtime CUDA EP.
- **Pip cai lai CPU wheel:** tach requirements va cai engine bang script co index ro rang.
- **ONNX Runtime co CUDA provider nhung mot so node roi ve CPU:** bat `session.disable_cpu_ep_fallback=1` va fail startup neu model khong chay tron ven tren CUDA EP.
- **ONNX detector dung GPU, VietOCR van CPU:** production strict mode fail startup neu mot ben khong dat.
- **Xung dot DLL ONNX Runtime/PyTorch tren Windows:** import Torch hoac preload DLL truoc khi tao ORT session; pin Torch cu128 va ORT CUDA 12.x; tach process neu can.
- **Model ONNX khac ket qua Paddle baseline:** so sanh box/toa do tren tap test truoc khi chap nhan artifact ONNX.
- **VietOCR khong tuong thich PyTorch moi:** chay model-load/OCR integration test va pin cap version da qua test.
- **GPU nhanh o model nhung API khong nhanh:** benchmark OCR-only va end-to-end rieng, profile tung stage.
- **VRAM spike/OOM khi nhieu request:** giu lock va mot model instance dot dau, sau do moi tang concurrency.
- **Ket qua GPU khac CPU nhe do numerical kernel:** danh gia bang accuracy/CER va diff tung mau, khong doi hoi text byte-identical.
- **GPU co mat nhung service roi ve CPU:** `OCR_GPU_REQUIRED=true`, startup fail va health hien actual device.

## 8. Deliverable cua dot chuyen doi

- Script cai dat Windows GPU co the chay lai.
- Requirements tach CPU/GPU va lock file version da test.
- Model detector ONNX da version hoa kem checksum va metadata export.
- Device detection strict va GPU smoke test luc startup.
- `/health` hien requested/actual device.
- Unit test device-selection va integration test GPU.
- Bao cao benchmark CPU/GPU gom accuracy, latency, throughput, VRAM va package versions.
- Huong dan deploy/rollback Windows Server.
- Artifact audit server: `nvidia-smi`, `nvcc`, Python, pip freeze, commit hash va test logs.

## 9. Tieu chi hoan thanh cuoi cung

Chi danh dau hoan thanh khi tat ca dieu sau dung:

- Server dung CUDA Toolkit 12.8 va driver tuong thich RTX 5060 Ti.
- ONNX Runtime CUDA detector va Torch deu chay inference/tensor test tren RTX 5060 Ti.
- Detector la `CUDAExecutionProvider` voi `cpu_fallback=false`, recognizer la `cuda:0` trong `/health`.
- Backend production khong co silent CPU fallback.
- Integration test va toan bo regression test lien quan deu pass.
- Accuracy gate va performance gate deu pass.
- Da thu rollback thanh cong.

## 10. Tai lieu tham chieu

- Paddle `cu128` package index (hien chi co Linux wheel 3.2.0): https://www.paddlepaddle.org.cn/packages/stable/cu128/paddlepaddle-gpu/
- Paddle2ONNX documentation: https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/legacy/paddle2onnx.html
- ONNX Runtime CUDA Execution Provider: https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html
- ONNX Runtime install/compatibility: https://onnxruntime.ai/docs/install/
- PyTorch previous versions and cu128 wheel command: https://pytorch.org/get-started/previous-versions/
- NVIDIA CUDA compatibility: https://docs.nvidia.com/deploy/cuda-compatibility/index.html
