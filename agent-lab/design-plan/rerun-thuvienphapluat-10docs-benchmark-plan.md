# Kế hoạch rerun benchmark 10 văn bản pháp luật từ Thư Viện Pháp Luật

## Mục tiêu

Tạo lại một bộ test 10 tài liệu văn bản pháp luật từ Thư Viện Pháp Luật, sinh lại ảnh đầu vào, đáp án nguồn, kết quả OCR baseline và kết quả OCR + LLM, rồi kiểm tra xem bộ test và kết quả có đủ tin cậy để đánh giá chất lượng OCR hay không.

Kết quả mong muốn không chỉ là có số phần trăm mới, mà là có bằng chứng rõ:

- 10 URL văn bản được chọn là duy nhất, truy cập được, và có nội dung nguồn trích xuất được.
- 10 mẫu sinh ra đúng từ 10 văn bản, ưu tiên page 1 của từng văn bản để tránh một văn bản chiếm nhiều mẫu.
- Đáp án nguồn trong artifact khớp với nội dung live được scrape tại thời điểm rerun.
- Baseline OCR, OCR + LLM, số correction và delta từng mẫu được lưu đầy đủ.
- Có thể giải thích vì sao LLM tăng ít, tăng nhiều, hoặc làm giảm điểm trên từng mẫu.

## Phạm vi

Trong phạm vi:

- Làm mới danh sách 10 URL từ `https://thuvienphapluat.vn/page/van-ban-tphcm.aspx` hoặc một listing pháp luật tương đương nếu listing hiện tại không đủ 10 văn bản hợp lệ.
- Lưu danh sách URL test mới vào artifact riêng, không ghi đè bộ cũ nếu chưa có lý do rõ.
- Sinh thư mục benchmark mới dưới `PaddleOCR/benchmark/thuvienphapluat_legal_ocr_10docs_runs/<timestamp>`.
- Lưu `manifest.json`, `report.json`, `report.md`, ảnh render, và file comparison OCR + LLM.
- So sánh điểm từng mẫu: baseline, LLM, delta, edit distance, source length, OCR length, correction count.

Ngoài phạm vi:

- Chưa tối ưu OCR engine.
- Chưa nới prompt LLM để sửa mạnh hơn.
- Chưa gọi đây là benchmark scan thật, vì bộ hiện tại render ảnh synthetic từ text website.

## Câu hỏi cần tự kiểm trước khi chạy

- Nếu điểm tăng thấp, nguyên nhân là LLM yếu hay vì lỗi OCR là mất chữ/layout mà patch-only không thể sửa?
- Nếu điểm tăng cao, có phải LLM đang sửa quá mạnh hoặc hallucinate không?
- Đáp án nguồn có thật sự từ trang live, hay artifact bị lệch do encoding/caching?
- 10 mẫu có đại diện cho 10 văn bản khác nhau không, hay vô tình lấy nhiều page từ cùng một văn bản?
- Có mẫu nào LLM làm giảm điểm không, và correction nào gây giảm?

## Quy trình đề xuất

1. Snapshot trạng thái hiện tại

   - Ghi lại `git status`.
   - Không xóa hoặc ghi đè thư mục benchmark cũ.
   - Xác định Python env dùng để chạy benchmark, ưu tiên `PaddleOCR/.venv`.

2. Chọn lại 10 văn bản

   - Fetch listing Thư Viện Pháp Luật.
   - Lấy các URL `/van-ban/...aspx` duy nhất.
   - Với mỗi URL, fetch trang chi tiết và kiểm tra có `#divContentDoc` hoặc đủ paragraph hợp lệ.
   - Chọn 10 văn bản đầu tiên hợp lệ.
   - Lưu danh sách URL mới vào một file có timestamp, ví dụ:
     `PaddleOCR/tests/test_files/thuvienphapluat_legal_10docs_YYYYMMDD_HHMMSS.json`.

3. Sinh lại benchmark baseline

   - Chạy `run_benchmark(document_urls=<10 URL>, max_pages_per_document=1)`.
   - Kiểm tra output có:
     - 10 sample.
     - 10 URL duy nhất.
     - Mỗi sample có `page_index == 1`.
     - 10 ảnh tồn tại.
     - `source_text` và `ocr_text` không rỗng.
   - Lưu kết quả vào thư mục timestamp mới.

4. Verify đáp án nguồn

   - Fetch lại từng URL live bằng cùng hàm `extract_document_source`.
   - Render lại page 1 trong thư mục tạm.
   - So sánh `source_text` live với `source_text` trong `report.json`.
   - Pass khi 10/10 khớp exact hoặc có giải thích cụ thể cho khác biệt do trang live thay đổi.

5. Rerun OCR + LLM comparison

   - Chạy comparison trên đúng `report.json` baseline mới.
   - Lưu file comparison mới có tên rõ model và scoring mode, ví dụ:
     `llm_comparison_filtered_relaxed_<model>.json`.
   - Bắt buộc lưu thêm chi tiết từng correction nếu script hiện tại chưa lưu:
     - `wrong`
     - `correct`
     - `replaced_count`
     - sample id
     - score before/after ở mức sample
   - Nếu không lưu được chi tiết correction, báo rõ đây là thiếu sót của artifact.

6. Phân tích kết quả

   - Tổng hợp:
     - weighted accuracy baseline.
     - weighted accuracy OCR + LLM.
     - mean accuracy baseline.
     - mean accuracy OCR + LLM.
     - total corrections.
     - số mẫu tăng, giảm, không đổi.
   - Với từng sample:
     - source length.
     - OCR length.
     - source - OCR shortfall.
     - base edit distance.
     - LLM edit distance.
     - distance saved.
     - correction count.
   - Đặc biệt soi các mẫu LLM làm giảm điểm.

7. Kết luận pass/fail

   Bộ benchmark mới được coi là đáng tin nếu:

   - 10/10 URL fetch được.
   - 10/10 đáp án nguồn khớp live source tại thời điểm rerun.
   - 10/10 OCR baseline chạy thành công.
   - 10/10 OCR + LLM chạy thành công hoặc lỗi được ghi rõ.
   - Có file kết quả đủ để audit từng sample.

   Kết quả LLM được coi là chấp nhận được cho chế độ an toàn nếu:

   - Weighted accuracy không giảm.
   - Số mẫu bị giảm điểm là 0 hoặc giảm rất nhỏ và có thể giải thích.
   - Corrections không sửa số văn bản/ngày/năm theo kiểu rủi ro nếu chưa có validator.
   - Không có dấu hiệu LLM thêm nội dung ngoài OCR gốc.

## Rủi ro

- Trang Thư Viện Pháp Luật có thể thay đổi nội dung hoặc chặn request, làm source live lệch artifact.
- Synthetic image không phản ánh đầy đủ tài liệu scan thật.
- Nếu chỉ lưu correction count mà không lưu chi tiết correction, không thể kết luận correction đúng/sai từng cặp.
- Nếu LLM được nới quyền sửa quá mạnh, điểm có thể tăng nhưng rủi ro pháp lý cũng tăng.

## Lệnh kiểm chứng dự kiến

Các lệnh cụ thể nên được xác nhận lại theo trạng thái script hiện tại trước khi chạy:

```powershell
cd C:\Indti\project-ocr\PaddleOCR
.\.venv\Scripts\python.exe -m pytest tests\test_thuvienphapluat_legal_ocr_10docs.py -q -ra
```

Do test này đang bị marker `resource_intensive`, nếu cần chạy thật phải bật env hoặc override marker theo cấu hình pytest hiện tại:

```powershell
$env:RUN_THUVIENPHAPLUAT_10DOCS_BENCHMARK = "1"
.\.venv\Scripts\python.exe -m pytest tests\test_thuvienphapluat_legal_ocr_10docs.py -m resource_intensive -q -ra
```

Nếu cần verify source live thủ công, dùng script ngắn gọi `extract_document_source` và `build_page_samples`, rồi so sánh `source_text` với artifact mới.

## Deliverable sau khi chạy

- File URL mới: `PaddleOCR/tests/test_files/thuvienphapluat_legal_10docs_<timestamp>.json`.
- Thư mục benchmark mới: `PaddleOCR/benchmark/thuvienphapluat_legal_ocr_10docs_runs/<timestamp>`.
- Báo cáo tóm tắt trong chat gồm:
  - điểm tổng.
  - bảng 10 mẫu.
  - nhận xét đáp án chuẩn/chưa chuẩn.
  - nhận xét LLM có đáng bật tiếp hay không.
  - test/lệnh đã chạy và lỗi còn lại nếu có.
