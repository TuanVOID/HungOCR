# Task list chuyen PaddleOCR sang GPU tren Windows Server RTX 5060 Ti

Tai lieu nguon:

- `C:\Indti\project-ocr\agent-lab\design-plan\paddleocr-windows-rtx5060ti-gpu-migration-plan.md`

Rang buoc co dinh:

- Windows Server native.
- NVIDIA RTX 5060 Ti 16 GB, Blackwell `sm_120`.
- CUDA Toolkit global 12.8; khong dung CUDA 12.9.
- Detector PP-OCRv5 chay bang ONNX Runtime `CUDAExecutionProvider`.
- VietOCR chay bang PyTorch `cu128`.
- Production GPU khong duoc silent fallback ve CPU.

## Quy uoc trang thai

- `[ ]`: Chua lam.
- `[~]`: Dang lam.
- `[x]`: Da hoan thanh va co bang chung.
- `[!]`: Bi chan, can ghi ro blocker.

Khi bat dau hoac hoan thanh task, cap nhat ca checkbox trong task va bang tong tien do ben duoi.

## Bang tong tien do

Cap nhat `Ngay cap nhat`, `Trang thai`, `Bang chung` sau moi lan lam viec.

| Task | Noi dung ngan | Trang thai | Ngay cap nhat | Bang chung / blocker |
|---|---|---|---|---|
| TASK-001 | Snapshot CPU baseline | Chua lam | - | - |
| TASK-002 | Tach requirements CPU/GPU | Chua lam | - | - |
| TASK-003 | Script setup Windows GPU | Chua lam | - | - |
| TASK-004 | Script setup/rollback CPU | Chua lam | - | - |
| TASK-005 | Xac dinh model detector | Chua lam | - | - |
| TASK-006 | Export detector ONNX | Chua lam | - | - |
| TASK-007 | ONNX detector adapter | Chua lam | - | - |
| TASK-008 | So sanh Paddle CPU/ONNX CPU | Chua lam | - | - |
| TASK-009 | Runtime device config | Chua lam | - | - |
| TASK-010 | Strict ONNX CUDA validation | Chua lam | - | - |
| TASK-011 | Strict VietOCR CUDA validation | Chua lam | - | - |
| TASK-012 | Startup va readiness | Chua lam | - | - |
| TASK-013 | Health endpoint GPU detail | Chua lam | - | - |
| TASK-014 | Env example va tai lieu | Chua lam | - | - |
| TASK-015 | Unit test device/health | Chua lam | - | - |
| TASK-016 | GPU integration test | Chua lam | - | - |
| TASK-017 | Benchmark CPU/GPU | Chua lam | - | - |
| TASK-018 | Runbook deploy/rollback | Chua lam | - | - |
| TASK-019 | Audit Windows GPU server | Chua lam | - | Chi lam tren server |
| TASK-020 | Cai GPU environment server | Chua lam | - | Chi lam tren server |
| TASK-021 | Test DLL va sm_120 | Chua lam | - | Chi lam tren server |
| TASK-022 | Chay backend GPU strict | Chua lam | - | Chi lam tren server |
| TASK-023 | Integration input that | Chua lam | - | Chi lam tren server |
| TASK-024 | Benchmark chinh thuc | Chua lam | - | Chi lam tren server |
| TASK-025 | Thu rollback | Chua lam | - | Chi lam tren server |
| TASK-026 | Rollout production | Chua lam | - | Chi lam tren server |
| TASK-027 | Profile tung stage | Chua lam | - | Sau migration |
| TASK-028 | Tune VietOCR batch | Chua lam | - | Sau migration |
| TASK-029 | Danh gia concurrency | Chua lam | - | Sau migration |
| TASK-030 | Danh gia FP16/TensorRT | Chua lam | - | Sau migration |

### Tom tat hien tai

- Tong task: `30`.
- Da hoan thanh: `0`.
- Dang lam: `0`.
- Bi chan: `0`.
- Chua lam: `30`.
- Task dang thuc hien: `Chua co`.
- Task tiep theo de xuat: `TASK-001`.

## Nhom A - Cong viec co the lam ngay trong repository

### TASK-001 - Snapshot dependency va hanh vi CPU hien tai

- [ ] Ghi lai Python version, `pip freeze`, Paddle/Torch version cua `.venv` hien tai.
- [ ] Chay test hien co va luu ket qua baseline.
- [ ] Chay mot bo OCR nho tren CPU, luu output va thoi gian de doi chieu.
- [ ] Ghi lai `git status` va commit hash.

Output:

- Artifact baseline co timestamp duoi `PaddleOCR/benchmark/gpu_migration_runs/<timestamp>/baseline/`.
- File gom environment, test result, OCR output va timing.

Pass khi:

- Co the xac dinh dung code, dependency va ket qua CPU truoc khi sua.

### TASK-002 - Tach dependency chung, CPU va GPU

Phu thuoc: `TASK-001`.

- [ ] Tao `PaddleOCR/requirements-base.txt` khong chua Paddle/Torch/ONNX Runtime engine.
- [ ] Tao `PaddleOCR/requirements-cpu.txt` cho moi truong CPU.
- [ ] Tao `PaddleOCR/requirements-gpu-cu128.txt` pin:
  - `torch==2.10.0`
  - `torchvision==0.25.0`
  - `onnxruntime-gpu==1.22.0`
  - VietOCR version da chon.
- [ ] Bao dam khong co lenh cai dependency chung nao ghi de wheel GPU bang wheel CPU.
- [ ] Chay `pip check` trong moi truong test sach.

Output:

- Ba requirements file co muc dich ro rang.

Pass khi:

- Moi truong CPU va GPU co the cai rieng, khong cai dong thoi `onnxruntime` va `onnxruntime-gpu`, khong cai Torch CPU trong profile GPU.

### TASK-003 - Tao script cai dat Windows GPU CUDA 12.8

Phu thuoc: `TASK-002`.

- [ ] Tao `PaddleOCR/scripts/setup_windows_gpu.ps1`.
- [ ] Bat buoc dung Python 3.11 x64 va duong dan `.venv-gpu`.
- [ ] Nang `pip`, `setuptools`, `wheel` trong virtualenv.
- [ ] Cai requirements chung.
- [ ] Cai PyTorch tu index `https://download.pytorch.org/whl/cu128`.
- [ ] Cai `onnxruntime-gpu` da pin.
- [ ] Chay `pip check` va in version cuoi cung.
- [ ] Script dung ngay khi phat hien wheel CPU hoac package xung dot.

Pass khi:

- Script co the chay lai tren moi truong sach va khong dung `pip` global.

### TASK-004 - Tao script cai dat/rollback CPU

Phu thuoc: `TASK-002`.

- [ ] Tao `PaddleOCR/scripts/setup_windows_cpu.ps1`.
- [ ] Dung virtualenv CPU rieng.
- [ ] Pin PaddlePaddle CPU va PyTorch CPU phu hop code hien tai.
- [ ] Them lenh smoke import va `pip check`.

Pass khi:

- Co the tao lai moi truong CPU ma khong anh huong `.venv-gpu`.

### TASK-005 - Xac dinh chinh xac model detector production

Phu thuoc: `TASK-001`.

- [ ] Ghi lai model name/model directory ma `TextDetection` hien tai tai xuong va su dung.
- [ ] Xac dinh day la PP-OCRv5 mobile hay server detector.
- [ ] Luu source URL, version, config va SHA-256 cac model file.
- [ ] Chon duy nhat mot model detector lam baseline migration.

Pass khi:

- Khong con gia dinh mo ho ve model nao phai export sang ONNX.

### TASK-006 - Tao quy trinh export PP-OCRv5 detector sang ONNX

Phu thuoc: `TASK-005`.

- [ ] Tao virtualenv export rieng, khong dung `.venv-gpu` production.
- [ ] Tao `PaddleOCR/scripts/export_detector_onnx.ps1`.
- [ ] Pin PaddlePaddle CPU va Paddle2ONNX version dung de export.
- [ ] Export model detector da chon sang ONNX.
- [ ] Luu opset, input/output names, dynamic/static shapes va SHA-256.
- [ ] Tao metadata file canh model, vi du `model.metadata.json`.
- [ ] Khong export model trong luc backend production khoi dong.

Output du kien:

- `PaddleOCR/models/onnx/PP-OCRv5_server_det/model.onnx` hoac ten model thuc te.
- Metadata va checksum.

Pass khi:

- ONNX checker doc model thanh cong va input/output contract duoc ghi ro.

### TASK-007 - Xay dung ONNX detector adapter

Phu thuoc: `TASK-006`.

- [ ] Tao module detector adapter co interface `predict(image)` tuong thich code trong `process_image_ocr()`.
- [ ] Tai su dung preprocessing `DetResizeForTest`, normalize, HWC-to-CHW hien co.
- [ ] Tao ONNX Runtime session theo provider duoc cau hinh.
- [ ] Chuyen output model qua DB postprocessing hien co.
- [ ] Tra ve `dt_polys`/boxes theo format ma `process_image_ocr()` dang doc.
- [ ] Khong nhung logic CUDA truc tiep vao route Flask.

Pass khi:

- Adapter chay duoc bang `CPUExecutionProvider` tren may dev hien tai va tra box hop le.

### TASK-008 - So sanh Paddle CPU detector voi ONNX CPU detector

Phu thuoc: `TASK-007`.

- [ ] Chon tap anh gom clean, rotated, low-quality va anh lon.
- [ ] Chay cung anh qua Paddle CPU detector va ONNX CPU detector.
- [ ] So sanh box count, toa do, reading order va crop output.
- [ ] Luu diff tung anh.
- [ ] Dieu tra moi sai le lon truoc khi chap nhan model ONNX.

Pass khi:

- Khong mat text region dang ke.
- Sai le box nam trong nguong duoc ghi ro va OCR text downstream khong giam qua gate accuracy.

### TASK-009 - Refactor cau hinh runtime device

Phu thuoc: `TASK-007`.

- [ ] Thay tuple mo ho trong `detect_ocr_devices()` bang mot runtime config co truong ro rang.
- [ ] Ho tro:
  - `OCR_DEVICE=auto|gpu|cpu`
  - `OCR_GPU_REQUIRED=true|false`
  - `OCR_GPU_INDEX`
  - `OCR_DETECTOR_BACKEND=onnxruntime`
  - `OCR_DETECTOR_ONNX_MODEL`
  - `OCR_ORT_DISABLE_CPU_FALLBACK`
- [ ] Validate gia tri env va duong dan model.
- [ ] Gia tri khong hop le phai fail startup.
- [ ] `auto` chi fallback CPU khi `OCR_GPU_REQUIRED=false`.

Pass khi:

- Hanh vi device selection co the unit test ma khong can GPU that.

### TASK-010 - Them strict ONNX CUDA validation

Phu thuoc: `TASK-009`.

- [ ] Preload CUDA/cuDNN DLL bang import Torch hoac `onnxruntime.preload_dlls()`.
- [ ] Kiem tra `CUDAExecutionProvider` ton tai.
- [ ] Tao session voi dung `device_id`.
- [ ] Dat `session.disable_cpu_ep_fallback=1` khi strict mode bat.
- [ ] Kiem tra provider thuc te cua session.
- [ ] Chay detector smoke inference truoc khi backend ready.
- [ ] Bat startup fail neu CUDA EP khong khoi tao hoac model can CPU fallback.

Pass khi:

- Cau hinh production GPU khong the tra `/health: ready` neu detector khong chay tron ven tren CUDA EP.

### TASK-011 - Them strict PyTorch/VietOCR CUDA validation

Phu thuoc: `TASK-009`.

- [ ] Kiem tra `torch.version.cuda`.
- [ ] Kiem tra `torch.cuda.is_available()` va GPU index.
- [ ] Kiem tra ten GPU va `torch.cuda.get_arch_list()`/smoke operation cho `sm_120`.
- [ ] Chay matmul/tensor operation va `torch.cuda.synchronize()`.
- [ ] Khoi tao VietOCR tren `cuda:<index>`.
- [ ] Chay mot crop text smoke recognition.
- [ ] Fail startup neu VietOCR khong chay duoc GPU trong strict mode.

Pass khi:

- Khong co `no kernel image is available`, DLL error hoac silent CPU fallback.

### TASK-012 - Chuan hoa startup va readiness

Phu thuoc: `TASK-010`, `TASK-011`.

- [ ] Startup theo thu tu: config -> preload DLL -> GPU smoke -> detector -> recognizer -> OCR smoke.
- [ ] Tach `liveness` va `readiness` neu can.
- [ ] Chi danh dau ready sau khi model that da inference thanh cong.
- [ ] Log mot lan requested device, actual provider/device, GPU name va framework versions.
- [ ] Khong log secret hoac toan bo environment.

Pass khi:

- Backend loi som va co thong bao ro khi GPU stack khong hop le.

### TASK-013 - Mo rong endpoint health

Phu thuoc: `TASK-012`.

- [ ] Them requested device va `gpu_required`.
- [ ] Them detector framework/provider/device/verified/cpu_fallback.
- [ ] Them recognizer framework/device/verified.
- [ ] Them GPU index/name.
- [ ] Khong tra model path noi bo, credential hoac env secret.

Pass khi:

- Operator co the xac nhan ca detector va recognizer dang dung GPU chi bang health response.

### TASK-014 - Cap nhat `.env.example` va tai lieu cau hinh

Phu thuoc: `TASK-009`, `TASK-013`.

- [ ] Them day du bien GPU/ONNX moi vao `.env.example`.
- [ ] Ghi ro cau hinh production:

```dotenv
OCR_DEVICE=gpu
OCR_GPU_REQUIRED=true
OCR_GPU_INDEX=0
OCR_DETECTOR_BACKEND=onnxruntime
OCR_DETECTOR_ONNX_MODEL=models/onnx/PP-OCRv5_server_det/model.onnx
OCR_ORT_DISABLE_CPU_FALLBACK=true
FLAGS_use_mkldnn=0
FLAGS_use_onednn=0
```

- [ ] Ghi ro `auto` khong duoc dung thay strict GPU trong production.

Pass khi:

- Mot operator moi co the cau hinh service ma khong can doc source code.

### TASK-015 - Unit test device selection va health

Phu thuoc: `TASK-009` den `TASK-013`.

- [ ] Test `cpu` explicit.
- [ ] Test `auto` co GPU va khong co GPU.
- [ ] Test strict GPU thieu CUDA EP.
- [ ] Test strict GPU voi Torch CPU wheel.
- [ ] Test GPU index khong ton tai.
- [ ] Test env value khong hop le.
- [ ] Test ONNX CPU fallback bi chan.
- [ ] Test health payload dung va khong lo secret.

Pass khi:

- Test chay duoc tren CI/may CPU bang monkeypatch, khong doi GPU that.

### TASK-016 - Them integration test danh rieng cho server GPU

Phu thuoc: `TASK-010` den `TASK-013`.

- [ ] Them pytest marker `gpu_integration`.
- [ ] Test Torch CUDA smoke.
- [ ] Test ONNX detector CUDA smoke voi CPU fallback tat.
- [ ] Test VietOCR model-load va recognition.
- [ ] Test OCR API end-to-end.
- [ ] Skip co giai thich tren may khong co GPU; khong skip tren job GPU bat buoc.

Pass khi:

- Job GPU fail neu bat ky stage nao roi ve CPU hoac khong inference duoc.

### TASK-017 - Them benchmark CPU/GPU co the lap lai

Phu thuoc: `TASK-008`, `TASK-013`.

- [ ] Mo rong benchmark de ghi cold start, warm latency, p50, p95, throughput.
- [ ] Warm-up it nhat 5 request.
- [ ] Chay it nhat 3 lan cung thu tu input.
- [ ] Ghi health payload, package versions, commit hash va model checksum.
- [ ] Tach OCR-only khoi thoi gian LLM/Ollama.
- [ ] Luu JSON/CSV va report Markdown.

Pass khi:

- Cung mot command co the tao report CPU va GPU de so sanh cong bang.

### TASK-018 - Viet runbook deploy va rollback Windows Server

Phu thuoc: `TASK-003`, `TASK-004`, `TASK-013`, `TASK-017`.

- [ ] Ghi lenh audit server.
- [ ] Ghi lenh tao `.venv-gpu`, cai dependency va model.
- [ ] Ghi cach chay service GPU o port tam `8093`.
- [ ] Ghi smoke test va benchmark rut gon.
- [ ] Ghi cach chuyen reverse proxy/service binding.
- [ ] Ghi cach rollback ve service CPU cu.
- [ ] Ghi vi tri log va artifact can giu khi loi.

Pass khi:

- Rollout va rollback co the thuc hien theo tai lieu, khong can sua package trong virtualenv CPU cu.

## Nhom B - Cong viec bat buoc chay tren Windows Server GPU

### TASK-019 - Audit phan cung va CUDA 12.8 tren server

- [ ] Chay `nvidia-smi` va xac nhan RTX 5060 Ti 16 GB.
- [ ] Chay `nvcc --version` va xac nhan Toolkit 12.8.
- [ ] Ghi driver version, Windows Server version, RAM va dung luong dia.
- [ ] Xac nhan Python 3.11 x64.
- [ ] Luu toan bo output vao artifact timestamp.

Pass khi:

- GPU/driver/Toolkit/Python dung rang buoc, khong co loi driver.

### TASK-020 - Cai moi truong GPU sach tren server

Phu thuoc: `TASK-003`, `TASK-019`.

- [ ] Chay `setup_windows_gpu.ps1`.
- [ ] Chay `pip check`.
- [ ] Xac nhan Torch la build `+cu128`.
- [ ] Xac nhan ONNX Runtime co `CUDAExecutionProvider`.
- [ ] Luu `pip freeze`.

Pass khi:

- Khong co Torch CPU wheel, `onnxruntime` CPU package hoac dependency conflict.

### TASK-021 - Kiem tra DLL va `sm_120`

Phu thuoc: `TASK-020`.

- [ ] Import Torch truoc ONNX Runtime trong process moi.
- [ ] Chay Torch tensor/matmul tren GPU.
- [ ] Chay ONNX detector session tren GPU.
- [ ] Kiem tra khong co `WinError 126/127`.
- [ ] Kiem tra khong co `Unsupported GPU architecture` hoac `no kernel image is available`.

Pass khi:

- Ca hai runtime chay cung process on dinh tren RTX 5060 Ti.

### TASK-022 - Chay backend GPU strict tren port tam

Phu thuoc: `TASK-012`, `TASK-020`, `TASK-021`.

- [ ] Dat cau hinh strict GPU.
- [ ] Khoi dong backend tren port `8093`.
- [ ] Kiem tra startup log.
- [ ] Kiem tra `/health` co `CUDAExecutionProvider`, `cuda:0`, `cpu_fallback=false`.
- [ ] Kiem tra VRAM allocation bang `nvidia-smi`.

Pass khi:

- Service ready va hai stage OCR deu duoc xac nhan tren GPU.

### TASK-023 - Chay integration test input that

Phu thuoc: `TASK-022`.

- [ ] Anh chu Viet ro.
- [ ] Anh lon hon 1500 px.
- [ ] Anh xoay 90/180/270 do.
- [ ] Anh low-quality.
- [ ] PDF nhieu trang trong gioi han.
- [ ] Theo doi log, VRAM va response.

Pass khi:

- 100% request thanh cong.
- Input co chu khong tra ket qua rong bat thuong.
- Khong CUDA/DLL/OOM error.

### TASK-024 - Chay benchmark CPU/GPU chinh thuc

Phu thuoc: `TASK-017`, `TASK-023`.

- [ ] Chay benchmark 40 anh tren CPU va GPU.
- [ ] Chay bo 10 van ban phap luat tren CPU va GPU.
- [ ] Chay moi profile it nhat 3 lan sau warm-up.
- [ ] Luu p50, p95, throughput, total time, CPU/RAM/GPU/VRAM.
- [ ] Luu accuracy/CER va diff tung sample.

Performance gate:

- [ ] 40/40 anh thanh cong.
- [ ] 10/10 tai lieu thanh cong.
- [ ] Weighted accuracy GPU khong thap hon CPU qua 0.2 diem phan tram.
- [ ] Warm total time GPU nhanh hon CPU it nhat 25%.
- [ ] p50 GPU thap hon CPU.
- [ ] p95 GPU khong xau hon CPU trong sequential mode.
- [ ] Khong co crash, OOM, CUDA/DLL error hay ket qua rong moi.

### TASK-025 - Thu rollback truoc production

Phu thuoc: `TASK-018`, `TASK-022`.

- [ ] Khoi dong song song service CPU cu va GPU moi.
- [ ] Chuyen test binding sang GPU.
- [ ] Chuyen lai CPU theo runbook.
- [ ] Xac nhan CPU service van hoat dong va virtualenv cu khong bi sua.

Pass khi:

- Rollback hoan thanh trong cua so thoi gian du kien va khong mat du lieu/cau hinh.

### TASK-026 - Rollout production co kiem soat

Phu thuoc: `TASK-024`, `TASK-025`.

- [ ] Chay smoke test ngay truoc rollout.
- [ ] Chuyen reverse proxy/service binding sang GPU.
- [ ] Theo doi error rate, latency, VRAM/RAM va hang doi request.
- [ ] Theo doi CUDA/DLL/OOM errors.
- [ ] Giu CPU service san sang rollback trong thoi gian theo doi.
- [ ] Ghi ket qua rollout va thoi diem chot production.

Pass khi:

- Service GPU on dinh, health dung, khong regression va performance gate van dat tren traffic thuc.

## Nhom C - Toi uu sau khi migration co ban da dat

Khong bat dau nhom nay truoc khi `TASK-024` va `TASK-026` dat.

### TASK-027 - Profile detector va recognizer rieng

- [ ] Do thoi gian preprocessing, detector, crop, VietOCR batch va postprocessing.
- [ ] Xac dinh bottleneck thuc te.

### TASK-028 - Dieu chinh VietOCR batch size

- [ ] Thu cac batch size trong gioi han VRAM 16 GB.
- [ ] So sanh latency, throughput, accuracy va peak VRAM.

### TASK-029 - Danh gia concurrency

- [ ] Thu concurrency 2 va 4.
- [ ] Danh gia tach lock ONNX Runtime/Torch.
- [ ] Them queue/backpressure va gioi han request neu can.
- [ ] Khong chap nhan OOM hoac p95 regression.

### TASK-030 - Danh gia FP16/TensorRT rieng

- [ ] Tao nhanh benchmark rieng.
- [ ] Co accuracy gate va rollback rieng.
- [ ] Khong tron thay doi nay vao migration GPU co ban.

## Thu tu thuc hien de xuat

1. `TASK-001` -> `TASK-005` -> `TASK-006` -> `TASK-007` -> `TASK-008`.
2. `TASK-002` -> `TASK-003` va `TASK-004` co the lam song song voi export model.
3. `TASK-009` -> `TASK-010` va `TASK-011` -> `TASK-012` -> `TASK-013`.
4. `TASK-014`, `TASK-015`, `TASK-016`, `TASK-017`, `TASK-018`.
5. Tren server: `TASK-019` -> `TASK-020` -> `TASK-021` -> `TASK-022` -> `TASK-023` -> `TASK-024`.
6. `TASK-025` -> `TASK-026`.
7. Chi sau do moi lam `TASK-027` den `TASK-030`.

## Definition of Done tong

- [ ] CUDA Toolkit van la 12.8.
- [ ] Detector dung `CUDAExecutionProvider`, `cpu_fallback=false`.
- [ ] VietOCR dung `cuda:0`.
- [ ] Strict GPU loi startup neu mot stage khong dung duoc GPU.
- [ ] Unit test va GPU integration test pass.
- [ ] Accuracy gate pass.
- [ ] GPU nhanh hon CPU it nhat 25% tren benchmark 40 anh.
- [ ] Rollback da duoc thu thanh cong.
- [ ] Runbook va artifact benchmark da duoc luu.
