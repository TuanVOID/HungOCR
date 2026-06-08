# Thư Viện Pháp Luật OCR Benchmark

- Generated at: `2026-06-08T15:39:45`
- Samples: `10`
- Weighted char accuracy: `81.88%`
- Mean sample accuracy: `82.24%`
- Weighted CER: `18.12%`
- Total source length: `30621`
- Total OCR length: `26323`

## Metric

Accuracy = `1 - Levenshtein(normalized_source, normalized_ocr) / max(len(source), len(ocr), 1)`.
Whitespace is collapsed, Unicode is normalized with NFKC, text is lowercased, and spaces around common punctuation are normalized before scoring.

## Samples

| Sample | Document | Page | Accuracy | CER | Source len | OCR len |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `01-01` | Quyết định 32/2026/QĐ-UBND hướng dẫn nội dung chi Quỹ Phòng chống thiên tai Hồ Chí Minh | 1 | 77.96% | 22.04% | 2899 | 2384 |
| `02-01` | Quyết định 3214/QĐ-UBND 2026 công bố thủ tục hành chính Hoạt động khoa học Sở Khoa học Hồ Chí Minh | 1 | 80.97% | 19.03% | 3379 | 2878 |
| `03-01` | Quyết định 3209/QĐ-UBND 2026 Quy trình thủ tục hành chính Giáo dục với nước ngoài Sở Giáo dục Hồ Chí Minh | 1 | 77.79% | 22.21% | 3251 | 2628 |
| `04-01` | Quyết định 3207/QĐ-UBND 2026 Quy trình thủ tục hành chính lĩnh vực Giảm nghèo Sở Nông nghiệp Hồ Chí Minh | 1 | 77.94% | 22.06% | 3237 | 2614 |
| `05-01` | Quyết định 31/2026/QĐ-UBND Hướng dẫn tiêu chuẩn xét tặng danh hiệu Gia đình văn hóa Hồ Chí Minh | 1 | 71.75% | 28.25% | 3388 | 2598 |
| `06-01` | Quyết định 3181/QĐ-UBND 2026 công bố thủ tục hành chính Viễn thông và Internet Sở Khoa học Hồ Chí Minh | 1 | 88.65% | 11.35% | 2801 | 2598 |
| `07-01` | Quyết định 3180/QĐ-UBND 2026 công bố thủ tục hành chính lĩnh vực Thủy lợi Sở Nông nghiệp Hồ Chí Minh | 1 | 82.11% | 17.89% | 3237 | 2785 |
| `08-01` | Quyết định 3182/QĐ-UBND 2026 công bố thủ tục hành chính Biến đổi khí hậu Sở Nông nghiệp Hồ Chí Minh | 1 | 88.09% | 11.91% | 2805 | 2606 |
| `09-01` | Quyết định 3183/QĐ-UBND 2026 công bố thủ tục hành chính Tiêu chuẩn đo lường Sở Khoa học Hồ Chí Minh | 1 | 88.68% | 11.32% | 2817 | 2615 |
| `10-01` | Quyết định 3099/QĐ-UBND 2026 công bố thủ tục hành chính Thủy sản Sở Nông nghiệp Hồ Chí Minh | 1 | 88.49% | 11.51% | 2807 | 2617 |