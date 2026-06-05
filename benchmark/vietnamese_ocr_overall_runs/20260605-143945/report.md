# Vietnamese OCR Overall Benchmark

- Generated at: `2026-06-05T14:49:26`
- Samples: `40`
- Weighted char accuracy: `38.52%`
- Mean sample accuracy: `28.91%`
- Weighted CER: `61.48%`
- Total source length: `69400`
- Total OCR length: `39571`

## Metric

Accuracy = `1 - Levenshtein(normalized_source, normalized_ocr) / max(len(source), len(ocr), 1)`.
Whitespace is collapsed and Unicode is normalized with NFKC before scoring.

## By Kind

| Kind | Count | Weighted Acc | Mean Acc |
| --- | ---: | ---: | ---: |
| formula | 5 | 11.36% | 17.56% |
| handwritten | 5 | 4.00% | 4.00% |
| legal | 20 | 40.00% | 39.99% |
| minutes | 5 | 21.38% | 23.79% |
| table | 5 | 25.96% | 25.96% |

## By Transform

| Transform | Count | Weighted Acc | Mean Acc |
| --- | ---: | ---: | ---: |
| clean | 8 | 86.33% | 72.65% |
| low_quality | 8 | 82.05% | 43.89% |
| rot180 | 8 | 21.02% | 21.28% |
| rot270 | 8 | 1.54% | 2.94% |
| rot90 | 8 | 1.67% | 3.79% |

## Samples

| Sample | Kind | Transform | Accuracy | CER | Source len | OCR len |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `legal-1-clean` | legal | clean | 86.72% | 13.28% | 3322 | 3130 |
| `legal-1-rot90` | legal | rot90 | 1.32% | 98.68% | 3322 | 53 |
| `legal-1-rot180` | legal | rot180 | 22.61% | 77.39% | 3322 | 3186 |
| `legal-1-rot270` | legal | rot270 | 1.32% | 98.68% | 3322 | 53 |
| `legal-1-low_quality` | legal | low_quality | 86.60% | 13.40% | 3322 | 3192 |
| `legal-2-clean` | legal | clean | 90.49% | 9.51% | 3449 | 3325 |
| `legal-2-rot90` | legal | rot90 | 1.45% | 98.55% | 3449 | 57 |
| `legal-2-rot180` | legal | rot180 | 20.64% | 79.36% | 3449 | 3222 |
| `legal-2-rot270` | legal | rot270 | 1.33% | 98.67% | 3449 | 55 |
| `legal-2-low_quality` | legal | low_quality | 90.11% | 9.89% | 3449 | 3356 |
| `legal-3-clean` | legal | clean | 86.92% | 13.08% | 3340 | 3137 |
| `legal-3-rot90` | legal | rot90 | 1.29% | 98.71% | 3340 | 53 |
| `legal-3-rot180` | legal | rot180 | 22.01% | 77.99% | 3340 | 3156 |
| `legal-3-rot270` | legal | rot270 | 1.29% | 98.71% | 3340 | 53 |
| `legal-3-low_quality` | legal | low_quality | 86.41% | 13.59% | 3340 | 3240 |
| `legal-4-clean` | legal | clean | 87.52% | 12.48% | 2861 | 2744 |
| `legal-4-rot90` | legal | rot90 | 1.36% | 98.64% | 2861 | 47 |
| `legal-4-rot180` | legal | rot180 | 21.15% | 78.85% | 2861 | 2804 |
| `legal-4-rot270` | legal | rot270 | 1.33% | 98.67% | 2861 | 45 |
| `legal-4-low_quality` | legal | low_quality | 87.98% | 12.02% | 2861 | 2796 |
| `handwritten-note-clean` | handwritten | clean | 0.00% | 100.00% | 150 | 0 |
| `handwritten-note-rot90` | handwritten | rot90 | 2.67% | 97.33% | 150 | 9 |
| `handwritten-note-rot180` | handwritten | rot180 | 17.33% | 82.67% | 150 | 137 |
| `handwritten-note-rot270` | handwritten | rot270 | 0.00% | 100.00% | 150 | 0 |
| `handwritten-note-low_quality` | handwritten | low_quality | 0.00% | 100.00% | 150 | 0 |
| `formula-sheet-clean` | formula | clean | 62.27% | 50.00% | 206 | 273 |
| `formula-sheet-rot90` | formula | rot90 | 2.43% | 97.57% | 206 | 11 |
| `formula-sheet-rot180` | formula | rot180 | 21.18% | 97.57% | 206 | 255 |
| `formula-sheet-rot270` | formula | rot270 | 1.94% | 98.06% | 206 | 9 |
| `formula-sheet-low_quality` | formula | low_quality | 0.00% | 100.00% | 206 | 0 |
| `table-invoice-clean` | table | clean | 75.69% | 24.31% | 218 | 172 |
| `table-invoice-rot90` | table | rot90 | 16.51% | 83.49% | 218 | 59 |
| `table-invoice-rot180` | table | rot180 | 24.31% | 75.69% | 218 | 168 |
| `table-invoice-rot270` | table | rot270 | 13.30% | 86.70% | 218 | 44 |
| `table-invoice-low_quality` | table | low_quality | 0.00% | 100.00% | 218 | 0 |
| `meeting-minutes-clean` | minutes | clean | 91.62% | 8.38% | 334 | 311 |
| `meeting-minutes-rot90` | minutes | rot90 | 3.29% | 96.71% | 334 | 17 |
| `meeting-minutes-rot180` | minutes | rot180 | 21.04% | 91.02% | 334 | 385 |
| `meeting-minutes-rot270` | minutes | rot270 | 2.99% | 97.01% | 334 | 17 |
| `meeting-minutes-low_quality` | minutes | low_quality | 0.00% | 100.00% | 334 | 0 |