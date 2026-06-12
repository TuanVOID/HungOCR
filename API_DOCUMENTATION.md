# Tài Liệu API - Dịch Vụ OCR & LLM Analysis

Dịch vụ này được xây dựng bằng **Flask**, chạy mặc định ở cổng **`5000`** (cấu hình qua biến `PORT` trong tệp `.env`). Dịch vụ hỗ trợ nhận diện ký tự quang học (OCR) từ hình ảnh, tài liệu PDF, DOCX, cùng khả năng sửa lỗi chính tả và tóm tắt văn bản bằng LLM (Ollama).

---

## 1. API Kiểm tra trạng thái dịch vụ (Health Check)
*   **Endpoint**: `GET /health`
*   **Response (JSON)**:
    ```json
    {
      "status": "ready",
      "engine": "extraction_ocr_engine"
    }
    ```

---

## 2. API Nhận diện ký tự quang học (Run OCR)
Nhận diện chữ viết từ hình ảnh, PDF hoặc tài liệu Word (DOCX). Hỗ trợ song song việc gửi văn bản nhận dạng qua LLM (Ollama) để tự động sửa các lỗi chính tả phổ biến do OCR gây ra.

*   **Endpoint**: `POST /ocr`
*   **Content-Type**: `multipart/form-data`
*   **Request Body**:
    *   `files` *(Tệp tin hoặc Danh sách tệp tin, Bắt buộc)*: Trường gửi các tệp tài liệu cần OCR (chấp nhận `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.docx`).
    *   `import_type` *(String, Tùy chọn)*: Chế độ nhận diện:
        *   `"clear"` *(Mặc định)*: Nhận diện nhanh chóng, không sửa lỗi chính tả bằng AI.
        *   `"complex_llm"`: Nhận diện chậm hơn nhưng kích hoạt sửa lỗi chính tả tự động bằng AI (Ollama).
    *   `layout_preserve` *(String, Tùy chọn)*: `"true"` hoặc `"false"` (mặc định là `"false"`). Nếu `"true"`, hệ thống sẽ cố gắng giữ nguyên bố cục căn lề ngang/khoảng cách của văn bản.
*   **Giới hạn**:
    *   Dung lượng mỗi file tối đa: 10MB (hoặc cấu hình qua `MAX_UPLOAD_FILE_SIZE_BYTES`).
    *   Tổng số trang xử lý của tất cả các file tải lên trong 1 yêu cầu không vượt quá 10 trang (cấu hình qua `MAX_PDF_PAGES`).
    *   Độ phân giải ảnh tối đa: 20,000,000 pixels.
*   **Response (JSON)**:
    ```json
    {
      "status": "success",
      "import_type": "clear",
      "import_type_label": "Rõ ràng (nhanh)",
      "layout_preserve": false,
      "llm_postprocess": false,
      "results": [
        {
          "filename": "document_sample.pdf",
          "status": "success",
          "pages": [
            {
              "page_number": 1,
              "text": "Nội dung văn bản nhận dạng được ở trang 1..."
            }
          ]
        }
      ]
    }
    ```
    *Nếu sử dụng chế độ `"complex_llm"`, cấu trúc của mỗi trang trong `pages` sẽ có thêm các trường:*
    *   `raw_text`: Văn bản gốc chưa sửa lỗi.
    *   `llm_status`: Trạng thái sửa lỗi (`"success"`, `"partial"`, hoặc `"failed"`).
    *   `llm_corrections`: Mảng chứa các cặp từ đã sửa lỗi: `[{"wrong": "từ_sai", "correct": "từ_đúng", "replaced_count": 1}]`.

---

## 3. API Tóm tắt nội dung văn bản (Summarize OCR Text)
Nhận đầu vào là kết quả nhận dạng từ API `/ocr`, gửi nội dung tới LLM (Ollama) để tóm tắt các nhóm nội dung chính của tài liệu.

*   **Endpoint**: `POST /summarize`
*   **Content-Type**: `application/json`
*   **Request Body**:
    ```json
    {
      "results": [
        {
          "filename": "document_sample.pdf",
          "status": "success",
          "pages": [
            {
              "page_number": 1,
              "text": "Nội dung văn bản dài cần tóm tắt..."
            }
          ]
        }
      ]
    }
    ```
*   **Response (JSON)**:
    ```json
    {
      "status": "success",
      "summaries": [
        {
          "filename": "document_sample.pdf",
          "sheet_title": "Tóm tắt document_sample",
          "status": "success",
          "detail": "1 phần gốc",
          "rows": [
            {
              "Nhóm nội dung": "Thông tin chung",
              "Nội dung chính": "Quyết định số 123/QĐ-UBND ngày 12/06/2026 của Ủy ban nhân dân tỉnh."
            },
            {
              "Nhóm nội dung": "Nhiệm vụ trọng tâm",
              "Nội dung chính": "Đẩy nhanh tiến độ số hóa dữ liệu hộ tịch trên toàn địa bàn tỉnh."
            }
          ]
        }
      ]
    }
    ```

---

## 4. API Xuất kết quả OCR gốc ra Excel (Export to XLSX)
Tạo và tải về tệp Excel chứa dữ liệu văn bản đã OCR.

*   **Endpoint**: `POST /export/xlsx`
*   **Content-Type**: `application/json`
*   **Request Body**: Nhận JSON payload chứa trường `results` tương tự cấu trúc gửi tới API `/summarize`.
*   **Response**: Trả về trực tiếp tệp Excel nhị phân để tải về máy khách (mimetype `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), tên tệp dạng `ocr-goc-{timestamp}.xlsx`.

---

## 5. API Xuất tóm tắt AI ra Excel (Export Summary to XLSX)
Tạo và tải về tệp Excel chứa bảng tóm tắt đã được AI phân tích.

*   **Endpoint**: `POST /export/summary-xlsx`
*   **Content-Type**: `application/json`
*   **Request Body**:
    ```json
    {
      "results": [...],
      "summary_results": [...]
    }
    ```
    *Lưu ý: Nếu không truyền `summary_results` (mảng tóm tắt từ API `/summarize`), backend sẽ tự động chạy lại phân tích tóm tắt dựa trên `results` trước khi tạo file Excel.*
*   **Response**: Trả về trực tiếp tệp Excel nhị phân để tải về máy khách (mimetype giống API xuất Excel OCR gốc), tên tệp dạng `tom-tat-ai-{timestamp}.xlsx`.

---

## 6. Ví Dụ Gọi API Bằng Python

```python
import requests

url = "http://localhost:5000/ocr"
image_path = "bien_ban_hop.png"

with open(image_path, "rb") as f:
    files = {"files": f}
    # Sử dụng chế độ complex_llm để kích hoạt AI sửa lỗi chính tả
    data_form = {"import_type": "complex_llm", "layout_preserve": "false"}
    response = requests.post(url, files=files, data=data_form)
    
if response.status_code == 200:
    ocr_data = response.json()
    for doc in ocr_data["results"]:
        print(f"Tệp: {doc['filename']}")
        for page in doc["pages"]:
            print(f"--- Trang {page['page_number']} ---")
            print(page["text"])
else:
    print(f"Lỗi: {response.status_code} - {response.text}")
```
