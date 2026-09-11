# Kết nối ứng dụng với dịch vụ olmOCR

Dịch vụ Docker cung cấp HTTP API bất đồng bộ tại cổng publish và yêu cầu bearer
key trong `OLMOCR_API_KEY`. Ứng dụng gọi dịch vụ phải hỗ trợ contract job cùng
khóa này; một bản ứng dụng cũ chỉ có luồng OCR đồng bộ không thể hoạt động chỉ
bằng cách đổi URL.

Sau khi Chatbot đã được cập nhật phần tích hợp olmOCR bất đồng bộ, việc chuyển
sang máy OCR mới chỉ cần cấu hình backend rồi rebuild/restart API:

```dotenv
OLMOCR_BASE_URL=http://127.0.0.1:8011
OLMOCR_API_KEY=<giá trị cùng tên trong .env của bộ Docker>
OCR_TIMEOUT_MS=900000
TOOL_PROXY_TIMEOUT_MS=960000
```

Giữ `OCR_BASE_URL` trỏ đến Docling hiện hữu. Luồng ứng dụng dùng Docling cho PDF
có text và dùng olmOCR cho trang scan/ảnh. Khóa chỉ đặt ở backend, không dùng biến
`NEXT_PUBLIC_` và không commit vào Git.

Nếu Chatbot và olmOCR ở hai máy khác nhau, dùng URL LAN của máy OCR, ví dụ
`http://192.168.1.50:8011`. Trên máy OCR, đặt `OLMOCR_BIND_IP` thành IP LAN đó và
giới hạn firewall để chỉ máy API được kết nối cổng 8011.

Sau khi đổi biến môi trường, cần restart tiến trình API vì tiến trình đang chạy
không tự đọc lại env. Kiểm tra cả ba tình huống trên ứng dụng thật: PDF có text,
PDF scan và PDF hỗn hợp được đính kèm trong chat.
