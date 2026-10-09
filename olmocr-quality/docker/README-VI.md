# olmOCR Docker độc lập

Thư mục này đóng gói olmOCR thành một dịch vụ Docker độc lập có xác thực. Dịch vụ
dùng model `olmOCR-2-7B-1025-FP8`, nhận job OCR qua HTTP và tự gỡ model khỏi GPU
sau `OLMOCR_IDLE_SECONDS` giây không có tác vụ (mặc định 30).

## Chuẩn bị máy đích

- Windows, Docker Desktop chạy Linux containers bằng WSL2 và Docker Compose hỗ
  trợ `gpus: all`.
- GPU NVIDIA. Bản portable đã được kiểm thử trên RTX 5060 Ti 16 GB.
- Khoảng 14 GB VRAM trống khi OCR, ít nhất 32 GB RAM và khoảng 70 GB SSD trống
  để chứa gói chuyển, image, model và cache.
- Docker Desktop được bật trước khi chạy bộ cài. Không cần cài riêng Python,
  Node.js hoặc CUDA Toolkit cho dịch vụ.

## Cài từ bộ portable

Chép nguyên thư mục `olmocr-docker-portable-v1` sang ổ SSD của máy đích. Không
tách các file model. Mở PowerShell trong thư mục đó rồi chạy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\verify.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\manage.ps1 status
```

`install.ps1` kiểm tra checksum, import image Docker, tạo `.env` cùng khóa API
ngẫu nhiên và khởi động container. Mặc định API chỉ được publish tại
`127.0.0.1:8011`; cổng model nội bộ không được publish.

Trạng thái `ready: true`, `model_state: unloaded` là bình thường. API đang sẵn
sàng còn model chưa chiếm GPU. Model tự nạp khi có job và tự gỡ sau
`OLMOCR_IDLE_SECONDS` giây rảnh.
Lần chạy lạnh đầu tiên có thể mất vài phút để nạp model và biên dịch kernel.

## Kiểm tra OCR và tự gỡ model

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\smoke.ps1 `
  -InputPdf 'C:\test\scan.pdf' -WaitIdle
```

Kết quả phải hoàn tất mà không fallback. Khi dùng `-WaitIdle`, script chờ và xác
nhận model quay lại trạng thái `unloaded`. Có thể đối chiếu VRAM bằng
`nvidia-smi` trước và sau.

## Vận hành

```powershell
.\manage.ps1 status
.\manage.ps1 logs
.\manage.ps1 start
.\manage.ps1 stop
```

Container dùng `restart: unless-stopped`. Bật Docker Desktop cùng Windows nếu
muốn dịch vụ tự chạy lại sau khi máy khởi động. Không dùng
`docker compose down -v` nếu cần giữ job, kết quả và cache trong Docker volumes.

Nếu API Chatbot nằm trên máy khác, đặt `OLMOCR_BIND_IP` trong `.env` thành IP LAN
của máy OCR, chạy lại `manage.ps1 start`, rồi chỉ mở TCP 8011 trên firewall cho
IP máy API. Không mở dịch vụ OCR trực tiếp ra Internet.

Xem [`APP-CONNECTION.md`](APP-CONNECTION.md) để cấu hình ứng dụng gọi dịch vụ.
Xem [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) để biết thành phần và giấy
phép đi kèm.

## Dùng model GPTQ-W4A16 cho GPU 12 GB

Model FP8 mặc định chiếm khoảng 11 GB VRAM khi OCR nên không chạy được trên GPU
12 GB. Có thể thay bằng bản lượng tử hóa 4-bit do cộng đồng làm (không phải của
AllenAI):

| | FP8 (mặc định) | GPTQ-W4A16 |
|---|---|---|
| Model | `allenai/olmOCR-2-7B-1025-FP8` | [`Charitarth/olmOCR-2-7B-1025-GPTQ-W4A16`](https://huggingface.co/Charitarth/olmOCR-2-7B-1025-GPTQ-W4A16) |
| Revision | `40bd7202494b8264ee17ada08b401b5aab7a9ce1` | `8a5d1482781d78304a065f239ff07135ad073bea` |
| Trọng số nạp vào GPU | 9,59 GiB | 6,65 GiB |
| VRAM đỉnh của tiến trình OCR | khoảng 11,1 GB | khoảng 8,2 GB |
| Tốc độ sinh chữ | khoảng 46 token/s | khoảng 53 token/s |

Đo trên RTX 5060 Ti 16 GB với Nghị định 137/2016/NĐ-CP (10 trang scan). GPTQ
nhanh hơn nhưng sai dấu tiếng Việt ở một số từ ngắn nhiều hơn FP8 (cả→cá,
nửa→nừa, chảy→chay). Nếu GPU đủ VRAM thì giữ FP8. GPTQ dùng kernel Marlin nên cần
GPU Ampere trở lên (RTX 30/40/50); không dùng cho RTX 20.

Sau khi đã cài bộ portable như trên, tại thư mục gói, tải đúng revision đã kiểm
thử (khoảng 6,5 GB) bằng chính image của dịch vụ:

```powershell
docker run --rm --entrypoint python3 -e HF_HUB_OFFLINE=0 `
  -v "${PWD}\models\olmocr-gptq-w4a16:/out" law-olmocr:portable-v1 -c `
  "from huggingface_hub import snapshot_download; snapshot_download('Charitarth/olmOCR-2-7B-1025-GPTQ-W4A16', revision='8a5d1482781d78304a065f239ff07135ad073bea', local_dir='/out')"
```

Kiểm tra SHA256 của cả 17 file theo `models-gptq-w4a16.sha256`:

```powershell
Get-Content .\models-gptq-w4a16.sha256 | ForEach-Object {
  $hash, $file = $_ -split '\s+', 2
  $actual = (Get-FileHash ".\models\olmocr-gptq-w4a16\$file" -Algorithm SHA256).Hash
  if ($actual.ToLowerInvariant() -ne $hash) { throw "Checksum mismatch: $file" }
}
'GPTQ-W4A16 verified'
```

Đổi model khi không có job đang chạy. Dịch vụ luôn đọc model tại `models/olmocr`:

```powershell
.\manage.ps1 stop
Rename-Item .\models\olmocr olmocr-fp8
Rename-Item .\models\olmocr-gptq-w4a16 olmocr
```

Trên GPU 12 GB, đặt `OLMOCR_GPU_MEMORY_UTILIZATION=0.70` trong `.env` rồi chạy
`.\manage.ps1 start`. Khi khởi động, vLLM đòi VRAM trống ít nhất bằng tổng VRAM
nhân hệ số này; KV cache đã cố định 384 MiB nên hệ số chỉ ảnh hưởng bước kiểm
tra đó. Chạy `smoke.ps1` như trên và xem `/data/vllm.log` phải có
`Using MarlinLinearKernel for CompressedTensorsWNA16` và `Model loading took 6.65 GiB`.

Sau khi đổi, `verify.ps1` sẽ báo lỗi vì nó kiểm tra bộ FP8 gốc; dùng
lệnh kiểm tra GPTQ ở trên thay thế. Muốn quay lại FP8 thì đổi tên ngược lại và
trả hệ số về giá trị cũ.

## Build lại từ source

Tại thư mục `olmocr-quality` của repository:

```powershell
docker build -f .\docker\Dockerfile -t law-olmocr:portable-v1 .
```

Model không được đưa vào image; Compose mount thư mục `models` ở chế độ chỉ đọc.
