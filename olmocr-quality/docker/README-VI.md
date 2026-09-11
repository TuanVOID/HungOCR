# olmOCR Docker độc lập

Thư mục này đóng gói olmOCR thành một dịch vụ Docker độc lập có xác thực. Dịch vụ
dùng model `olmOCR-2-7B-1025-FP8`, nhận job OCR qua HTTP và tự gỡ model khỏi GPU
sau 300 giây không có tác vụ.

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
sàng còn model chưa chiếm GPU. Model tự nạp khi có job và tự gỡ sau năm phút rảnh.
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

## Build lại từ source

Tại thư mục `olmocr-quality` của repository:

```powershell
docker build -f .\docker\Dockerfile -t law-olmocr:portable-v1 .
```

Model không được đưa vào image; Compose mount thư mục `models` ở chế độ chỉ đọc.
