# Thư Viện Pháp Luật OCR Benchmark

- Generated at: `2026-06-08T13:27:42`
- Samples: `10`
- Weighted char accuracy: `79.88%`
- Mean sample accuracy: `80.57%`
- Weighted CER: `20.12%`
- Total source length: `31802`
- Total OCR length: `26762`

## Metric

Accuracy = `1 - Levenshtein(normalized_source, normalized_ocr) / max(len(source), len(ocr), 1)`.
Whitespace is collapsed and Unicode is normalized with NFKC before scoring.

## Samples

| Sample | Document | Page | Accuracy | CER | Source len | OCR len |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `01-01` | Quyết định 3207/QĐ-UBND 2026 Quy trình thủ tục hành chính lĩnh vực Giảm nghèo Sở Nông nghiệp Hồ Chí Minh | 1 | 77.00% | 23.00% | 3322 | 2653 |
| `02-01` | Quyết định 3214/QĐ-UBND 2026 công bố thủ tục hành chính Hoạt động khoa học Sở Khoa học Hồ Chí Minh | 1 | 79.91% | 20.09% | 3449 | 2909 |
| `03-01` | Quyết định 3209/QĐ-UBND 2026 Quy trình thủ tục hành chính Giáo dục với nước ngoài Sở Giáo dục Hồ Chí Minh | 1 | 76.86% | 23.14% | 3340 | 2669 |
| `04-01` | Quyết định 3181/QĐ-UBND 2026 công bố thủ tục hành chính Viễn thông và Internet Sở Khoa học Hồ Chí Minh | 1 | 86.12% | 13.88% | 2861 | 2640 |
| `05-01` | Quyết định 3099/QĐ-UBND 2026 công bố thủ tục hành chính Thủy sản Sở Nông nghiệp Hồ Chí Minh | 1 | 87.13% | 12.87% | 2867 | 2653 |
| `06-01` | Quyết định 3096/QĐ-UBND 2026 công bố thủ tục hành chính Sở Công Thương Hồ Chí Minh | 1 | 71.83% | 28.17% | 4040 | 3112 |
| `07-01` | Quyết định 3098/QĐ-UBND 2026 công bố thủ tục hành chính Thủy lợi Sở Nông nghiệp Hồ Chí Minh | 1 | 85.99% | 14.01% | 3019 | 2752 |
| `08-01` | Quyết định 3116/QĐ-UBND bãi bỏ Quyết định 24/2024/QĐ-UBND Hồ Chí Minh | 1 | 82.58% | 17.42% | 2732 | 2341 |
| `09-01` | Quyết định 3043/QĐ-UBND 2026 bãi bỏ Chỉ thị 27/2012/CT-UBND Hồ Chí Minh | 1 | 88.03% | 11.97% | 2640 | 2448 |
| `10-01` | Kế hoạch 219/KH-UBND 2026 kiểm tra chất lượng nước sạch sử dụng cho mục đích sinh hoạt Hồ Chí Minh | 1 | 70.30% | 29.70% | 3532 | 2585 |