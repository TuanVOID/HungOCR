# Thư Viện Pháp Luật OCR Benchmark

- Generated at: `2026-06-05T14:26:34`
- Samples: `10`
- Weighted char accuracy: `78.08%`
- Mean sample accuracy: `78.26%`
- Weighted CER: `21.92%`
- Total source length: `25288`
- Total OCR length: `20466`

## Metric

Accuracy = `1 - Levenshtein(normalized_source, normalized_ocr) / max(len(source), len(ocr), 1)`.
Whitespace is collapsed and Unicode is normalized with NFKC before scoring.

## Samples

| Sample | Document | Page | Accuracy | CER | Source len | OCR len |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `01-01` | Quyết định 3207/QĐ-UBND 2026 Quy trình thủ tục hành chính lĩnh vực Giảm nghèo Sở Nông nghiệp Hồ Chí Minh | 1 | 77.00% | 23.00% | 3322 | 2653 |
| `01-02` | Quyết định 3207/QĐ-UBND 2026 Quy trình thủ tục hành chính lĩnh vực Giảm nghèo Sở Nông nghiệp Hồ Chí Minh | 2 | 69.07% | 30.93% | 2021 | 1447 |
| `01-03` | Quyết định 3207/QĐ-UBND 2026 Quy trình thủ tục hành chính lĩnh vực Giảm nghèo Sở Nông nghiệp Hồ Chí Minh | 3 | 65.56% | 34.44% | 2790 | 1895 |
| `01-04` | Quyết định 3207/QĐ-UBND 2026 Quy trình thủ tục hành chính lĩnh vực Giảm nghèo Sở Nông nghiệp Hồ Chí Minh | 4 | 80.36% | 19.64% | 2220 | 1829 |
| `01-05` | Quyết định 3207/QĐ-UBND 2026 Quy trình thủ tục hành chính lĩnh vực Giảm nghèo Sở Nông nghiệp Hồ Chí Minh | 5 | 81.48% | 18.52% | 1625 | 1349 |
| `01-06` | Quyết định 3207/QĐ-UBND 2026 Quy trình thủ tục hành chính lĩnh vực Giảm nghèo Sở Nông nghiệp Hồ Chí Minh | 6 | 83.25% | 16.75% | 1707 | 1439 |
| `02-01` | Quyết định 3214/QĐ-UBND 2026 công bố thủ tục hành chính Hoạt động khoa học Sở Khoa học Hồ Chí Minh | 1 | 79.91% | 20.09% | 3449 | 2909 |
| `02-02` | Quyết định 3214/QĐ-UBND 2026 công bố thủ tục hành chính Hoạt động khoa học Sở Khoa học Hồ Chí Minh | 2 | 76.57% | 23.43% | 2164 | 1720 |
| `02-03` | Quyết định 3214/QĐ-UBND 2026 công bố thủ tục hành chính Hoạt động khoa học Sở Khoa học Hồ Chí Minh | 3 | 92.53% | 7.47% | 2650 | 2556 |
| `03-01` | Quyết định 3209/QĐ-UBND 2026 Quy trình thủ tục hành chính Giáo dục với nước ngoài Sở Giáo dục Hồ Chí Minh | 1 | 76.86% | 23.14% | 3340 | 2669 |