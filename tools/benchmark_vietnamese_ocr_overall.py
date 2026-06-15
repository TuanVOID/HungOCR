"""
Overall Vietnamese OCR benchmark.

This benchmark mixes multiple Vietnamese document styles into one 40-image set:
- real legal text scraped from Thư Viện Pháp Luật
- handwritten-style notes
- formula-heavy pages
- table/invoice-like layouts
- mixed meeting/minutes style pages

Each base document is rendered into five variants:
clean, rotate-90, rotate-180, rotate-270, and low-quality.

The benchmark compares OCR output against the known source text using a
normalized character-level Levenshtein accuracy metric.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import tempfile
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from tools.ocr_benchmark_common import (
    DEFAULT_CANDIDATE_DOCS,
    DEFAULT_LISTING_URL,
    DEFAULT_PAGE_HEIGHT,
    DEFAULT_PAGE_WIDTH,
    DEFAULT_SERVER_URL,
    build_page_samples,
    call_local_ocr,
    extract_document_source,
    fetch_listing_urls,
    get_font,
    make_session,
    normalize_for_scoring,
    score_text_pair,
    slugify,
)


DEFAULT_OUTPUT_ROOT = ROOT_DIR / "benchmark" / "vietnamese_ocr_overall_runs"
DEFAULT_SAMPLE_COUNT = 40
DEFAULT_BASE_DOC_COUNT = 4
DEFAULT_MARGIN_X = 90
DEFAULT_MARGIN_Y = 90
DEFAULT_FONT_SIZE = 26
DEFAULT_LINE_SPACING = 1.24
HANDWRITING_FONT = "segoepr.ttf"
TABLE_FONT = "arial.ttf"
FORMULA_FONT = "times.ttf"
PRINT_FONT = "times.ttf"


@dataclass
class BaseScenario:
    scenario_id: str
    kind: str
    title: str
    paragraphs: list[str] = field(default_factory=list)
    table_headers: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    font_name: str = PRINT_FONT
    background: str = "white"
    foreground: str = "black"


@dataclass
class OverallSample:
    sample_id: str
    scenario_id: str
    kind: str
    transform: str
    title: str
    image_path: str
    source_text: str
    ocr_text: str = ""
    accuracy: float = 0.0
    cer: float = 0.0
    edit_distance: int = 0
    source_length: int = 0
    ocr_length: int = 0


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    return " ".join(text.split())


def font_path(font_name: str) -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / font_name


def get_named_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    path = font_path(font_name)
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return get_font(size)


def wrap_text(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = normalize_text(text)
    if not text:
        return [""]

    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        if draw.textlength(word, font=font) <= max_width:
            current = word
            continue

        fragment = ""
        for char in word:
            candidate = fragment + char
            if draw.textlength(candidate, font=font) <= max_width or not fragment:
                fragment = candidate
            else:
                lines.append(fragment)
                fragment = char
        current = fragment

    if current:
        lines.append(current)

    return lines or [""]


def line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    return max((bbox[3] - bbox[1]) + 8, 24)


def render_text_page(
    paragraphs: Sequence[str],
    output_path: Path,
    font_name: str,
    font_size: int,
    background: str,
    foreground: str,
    page_width: int = DEFAULT_PAGE_WIDTH,
    page_height: int = DEFAULT_PAGE_HEIGHT,
    margin_x: int = DEFAULT_MARGIN_X,
    margin_y: int = DEFAULT_MARGIN_Y,
    line_spacing: float = DEFAULT_LINE_SPACING,
) -> None:
    image = Image.new("RGB", (page_width, page_height), background)
    draw = ImageDraw.Draw(image)
    font = get_named_font(font_name, font_size)
    step = max(1, math.floor(line_height(draw, font) * line_spacing))
    max_width = page_width - (margin_x * 2)
    y = margin_y

    for paragraph in paragraphs:
        paragraph = normalize_text(paragraph)
        if not paragraph:
            y += max(step // 2, 10)
            continue
        for line in wrap_text(paragraph, draw, font, max_width):
            draw.text((margin_x, y), line, fill=foreground, font=font)
            y += step
        y += max(step // 3, 6)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def render_table_page(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    output_path: Path,
    font_name: str,
    font_size: int,
    background: str,
    foreground: str,
    page_width: int = DEFAULT_PAGE_WIDTH,
    page_height: int = DEFAULT_PAGE_HEIGHT,
    margin_x: int = DEFAULT_MARGIN_X,
    margin_y: int = DEFAULT_MARGIN_Y,
) -> None:
    image = Image.new("RGB", (page_width, page_height), background)
    draw = ImageDraw.Draw(image)
    font = get_named_font(font_name, font_size)
    header_font = get_named_font(font_name, font_size + 2)

    cols = max(1, len(headers))
    col_width = (page_width - (margin_x * 2)) // cols
    row_height = max(line_height(draw, font) + 18, 56)
    table_width = col_width * cols
    left = margin_x
    top = margin_y

    def draw_cell_text(text: str, x0: int, y0: int, width: int, height: int, cell_font: ImageFont.ImageFont, bold: bool = False) -> None:
        text = normalize_text(text)
        lines = wrap_text(text, draw, cell_font, width - 18)
        text_h = len(lines) * line_height(draw, cell_font)
        text_y = y0 + max((height - text_h) // 2, 8)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=cell_font)
            text_w = bbox[2] - bbox[0]
            text_x = x0 + max((width - text_w) // 2, 8)
            draw.text((text_x, text_y), line, fill=foreground, font=cell_font)
            text_y += line_height(draw, cell_font)

    # Title line above the table.
    draw.text((margin_x, 40), normalize_text(headers[0] if headers else "Bảng dữ liệu"), fill=foreground, font=header_font)

    # Header row.
    for idx, header in enumerate(headers):
        x0 = left + (idx * col_width)
        x1 = x0 + col_width
        draw.rectangle([x0, top, x1, top + row_height], outline=foreground, width=2)
        draw_cell_text(header, x0, top, col_width, row_height, header_font)

    y = top + row_height
    for row in rows:
        for idx in range(cols):
            x0 = left + (idx * col_width)
            x1 = x0 + col_width
            draw.rectangle([x0, y, x1, y + row_height], outline=foreground, width=2)
            cell_text = row[idx] if idx < len(row) else ""
            draw_cell_text(cell_text, x0, y, col_width, row_height, font)
        y += row_height

    # Outer border
    draw.rectangle([left, top, left + table_width, y], outline=foreground, width=3)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def apply_transform(image: Image.Image, transform: str, background: str = "white") -> Image.Image:
    transform = transform.lower()
    if transform == "clean":
        return image
    if transform == "rot90":
        return image.rotate(90, expand=True, fillcolor=background)
    if transform == "rot180":
        return image.rotate(180, expand=True, fillcolor=background)
    if transform == "rot270":
        return image.rotate(270, expand=True, fillcolor=background)
    if transform == "low_quality":
        width, height = image.size
        small = image.resize((max(1, int(width * 0.55)), max(1, int(height * 0.55))), Image.Resampling.BILINEAR)
        restored = small.resize((width, height), Image.Resampling.BICUBIC)
        blurred = restored.filter(ImageFilter.GaussianBlur(radius=1.1))
        enhancer = ImageEnhance.Contrast(blurred)
        degraded = enhancer.enhance(0.88)
        noise = Image.effect_noise((width, height), 9).convert("L")
        noise_rgb = Image.merge("RGB", (noise, noise, noise))
        blended = Image.blend(degraded, noise_rgb, alpha=0.06)
        buffer = BytesIO()
        blended.save(buffer, format="JPEG", quality=42, optimize=True)
        buffer.seek(0)
        return Image.open(buffer).convert("RGB")
    raise ValueError(f"Unknown transform: {transform}")


def load_legal_base_scenarios(session, listing_url: str, count: int) -> list[BaseScenario]:
    urls = fetch_listing_urls(session, listing_url, count)
    scenarios: list[BaseScenario] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for index, url in enumerate(urls, start=1):
            document = extract_document_source(session, url)
            # Reuse the legal benchmark renderer to get a realistic first page sample.
            samples = build_page_samples(
                [document],
                output_dir=tmp_path / f"doc_{index}",
                max_images=1,
                page_width=DEFAULT_PAGE_WIDTH,
                page_height=DEFAULT_PAGE_HEIGHT,
                margin_x=DEFAULT_MARGIN_X,
                margin_y=DEFAULT_MARGIN_Y,
                line_spacing=1.28,
                font_size=26,
            )
            if not samples:
                continue
            first_sample = samples[0]
            scenarios.append(
                BaseScenario(
                    scenario_id=f"legal-{index}",
                    kind="legal",
                    title=document.title,
                    paragraphs=[first_sample.source_text],
                    font_name=PRINT_FONT,
                )
            )
    return scenarios


def build_synthetic_scenarios() -> list[BaseScenario]:
    return [
        BaseScenario(
            scenario_id="handwritten-note",
            kind="handwritten",
            title="Ghi chú viết tay",
            paragraphs=[
                "Ghi chú cuộc họp",
                "Sáng mai 8 giờ họp tại phòng 302.",
                "Mang theo CCCD, hồ sơ photo và bút xanh.",
                "Nếu mưa lớn thì nhắn lại trước 7 giờ 30.",
                "Cảm ơn mọi người.",
            ],
            font_name=HANDWRITING_FONT,
            background="#fcf7ef",
        ),
        BaseScenario(
            scenario_id="formula-sheet",
            kind="formula",
            title="Bảng công thức tiếng Việt",
            paragraphs=[
                "TỔNG HỢP CÔNG THỨC",
                "Diện tích hình tròn: S = πr²",
                "Chu vi hình tròn: C = 2πr",
                "Định lý Pitago: a² + b² = c²",
                "Nghiệm phương trình bậc hai: x = (-b ± √(b² - 4ac)) / 2a",
                "Ghi chú: kiểm tra ký hiệu trước khi nhập liệu.",
            ],
            font_name=FORMULA_FONT,
        ),
        BaseScenario(
            scenario_id="table-invoice",
            kind="table",
            title="Bảng hóa đơn tiếng Việt",
            table_headers=["STT", "Nội dung", "ĐVT", "SL", "Đơn giá", "Thành tiền"],
            table_rows=[
                ["1", "In tài liệu", "bộ", "2", "45.000", "90.000"],
                ["2", "Scan màu", "trang", "18", "3.500", "63.000"],
                ["3", "Đóng gáy", "cuốn", "1", "25.000", "25.000"],
                ["4", "Giao nhận", "lần", "1", "20.000", "20.000"],
            ],
            font_name=TABLE_FONT,
        ),
        BaseScenario(
            scenario_id="meeting-minutes",
            kind="minutes",
            title="Biên bản làm việc",
            paragraphs=[
                "BIÊN BẢN LÀM VIỆC",
                "1. Thời gian: 14 giờ 00 ngày 05/06/2026.",
                "2. Địa điểm: Phòng họp tầng 3.",
                "3. Thành phần: đại diện phòng Kế hoạch, phòng Kế toán và bộ phận kỹ thuật.",
                "4. Nội dung:",
                "- Thống nhất chốt số liệu trong ngày.",
                "- Rà soát lại danh sách hồ sơ còn thiếu.",
                "- Hoàn thiện báo cáo trước 17 giờ.",
                "Biên bản kết thúc lúc 15 giờ 20 cùng ngày.",
            ],
            font_name=PRINT_FONT,
        ),
    ]


def build_overall_scenarios(session, listing_url: str, base_doc_count: int) -> list[BaseScenario]:
    legal_scenarios = load_legal_base_scenarios(session, listing_url, base_doc_count)
    synthetic_scenarios = build_synthetic_scenarios()
    scenarios = legal_scenarios + synthetic_scenarios
    if len(scenarios) < 8:
        raise RuntimeError("Need at least 8 base scenarios to build the 40-image overall benchmark.")
    return scenarios[:8]


def scenario_source_text(scenario: BaseScenario) -> str:
    if scenario.kind == "table":
        rows = [scenario.table_headers] + scenario.table_rows
        flat = []
        for row in rows:
            flat.append(" | ".join(normalize_text(cell) for cell in row))
        return "\n".join(flat)
    return "\n".join(normalize_text(p) for p in scenario.paragraphs if normalize_text(p))


def render_scenario_image(scenario: BaseScenario, output_path: Path) -> None:
    if scenario.kind == "table":
        render_table_page(
            headers=scenario.table_headers,
            rows=scenario.table_rows,
            output_path=output_path,
            font_name=scenario.font_name,
            font_size=DEFAULT_FONT_SIZE,
            background=scenario.background,
            foreground=scenario.foreground,
        )
    else:
        render_text_page(
            paragraphs=scenario.paragraphs,
            output_path=output_path,
            font_name=scenario.font_name,
            font_size=DEFAULT_FONT_SIZE,
            background=scenario.background,
            foreground=scenario.foreground,
        )


def build_samples(
    scenarios: Sequence[BaseScenario],
    output_dir: Path,
    transforms: Sequence[str],
) -> list[OverallSample]:
    samples: list[OverallSample] = []
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    for scenario in scenarios:
        base_text = scenario_source_text(scenario)
        for transform in transforms:
            sample_id = f"{scenario.scenario_id}-{transform}"
            image_name = f"{sample_id}-{slugify(scenario.title)}.png"
            image_path = images_dir / image_name

            base_render_path = image_path.with_suffix(".base.png")
            render_scenario_image(scenario, base_render_path)
            base_image = Image.open(base_render_path).convert("RGB")
            transformed = apply_transform(base_image, transform, background=scenario.background)
            transformed.save(image_path)
            try:
                base_render_path.unlink()
            except Exception:
                pass

            samples.append(
                OverallSample(
                    sample_id=sample_id,
                    scenario_id=scenario.scenario_id,
                    kind=scenario.kind,
                    transform=transform,
                    title=scenario.title,
                    image_path=str(image_path),
                    source_text=base_text,
                    source_length=len(normalize_for_scoring(base_text)),
                )
            )
    return samples


def write_manifest(output_dir: Path, scenarios: Sequence[BaseScenario], samples: Sequence[OverallSample], listing_url: str) -> Path:
    manifest_path = output_dir / "manifest.json"
    manifest = {
        "listing_url": listing_url,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_scenarios": [asdict(scenario) for scenario in scenarios],
        "samples": [asdict(sample) for sample in samples],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def summarize_by_key(samples: Sequence[OverallSample], key: str) -> list[dict]:
    buckets: dict[str, list[OverallSample]] = {}
    for sample in samples:
        buckets.setdefault(getattr(sample, key), []).append(sample)

    rows: list[dict] = []
    for bucket_key, bucket_samples in sorted(buckets.items(), key=lambda item: item[0]):
        total_source = sum(sample.source_length for sample in bucket_samples)
        total_distance = sum(sample.edit_distance for sample in bucket_samples)
        weighted_accuracy = 1.0 if total_source == 0 else max(0.0, 1.0 - (total_distance / total_source))
        mean_accuracy = sum(sample.accuracy for sample in bucket_samples) / len(bucket_samples)
        rows.append(
            {
                key: bucket_key,
                "count": len(bucket_samples),
                "weighted_accuracy": weighted_accuracy,
                "mean_accuracy": mean_accuracy,
            }
        )
    return rows


def write_report(output_dir: Path, samples: Sequence[OverallSample]) -> tuple[Path, Path]:
    report_md = output_dir / "report.md"
    report_json = output_dir / "report.json"

    total_source = sum(sample.source_length for sample in samples)
    total_distance = sum(sample.edit_distance for sample in samples)
    total_ocr = sum(sample.ocr_length for sample in samples)
    weighted_accuracy = 1.0 if total_source == 0 else max(0.0, 1.0 - (total_distance / total_source))
    weighted_cer = 0.0 if total_source == 0 else total_distance / total_source
    mean_accuracy = sum(sample.accuracy for sample in samples) / len(samples) if samples else 0.0

    by_kind = summarize_by_key(samples, "kind")
    by_transform = summarize_by_key(samples, "transform")

    lines = [
        "# Vietnamese OCR Overall Benchmark",
        "",
        f"- Generated at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Samples: `{len(samples)}`",
        f"- Weighted char accuracy: `{weighted_accuracy * 100:.2f}%`",
        f"- Mean sample accuracy: `{mean_accuracy * 100:.2f}%`",
        f"- Weighted CER: `{weighted_cer * 100:.2f}%`",
        f"- Total source length: `{total_source}`",
        f"- Total OCR length: `{total_ocr}`",
        "",
        "## Metric",
        "",
        "Accuracy = `1 - Levenshtein(normalized_source, normalized_ocr) / max(len(source), len(ocr), 1)`.",
        "Whitespace is collapsed and Unicode is normalized with NFKC before scoring.",
        "",
        "## By Kind",
        "",
        "| Kind | Count | Weighted Acc | Mean Acc |",
        "| --- | ---: | ---: | ---: |",
    ]

    for row in by_kind:
        lines.append(
            f"| {row['kind']} | {row['count']} | {row['weighted_accuracy'] * 100:.2f}% | {row['mean_accuracy'] * 100:.2f}% |"
        )

    lines += [
        "",
        "## By Transform",
        "",
        "| Transform | Count | Weighted Acc | Mean Acc |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in by_transform:
        lines.append(
            f"| {row['transform']} | {row['count']} | {row['weighted_accuracy'] * 100:.2f}% | {row['mean_accuracy'] * 100:.2f}% |"
        )

    lines += [
        "",
        "## Samples",
        "",
        "| Sample | Kind | Transform | Accuracy | CER | Source len | OCR len |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for sample in samples:
        lines.append(
            f"| `{sample.sample_id}` | {sample.kind} | {sample.transform} | "
            f"{sample.accuracy * 100:.2f}% | {sample.cer * 100:.2f}% | "
            f"{sample.source_length} | {sample.ocr_length} |"
        )

    report_md.write_text("\n".join(lines), encoding="utf-8")
    report_json.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "weighted_accuracy": weighted_accuracy,
                "mean_accuracy": mean_accuracy,
                "weighted_cer": weighted_cer,
                "samples": [asdict(sample) for sample in samples],
                "by_kind": by_kind,
                "by_transform": by_transform,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_md, report_json


def run_overall_benchmark(
    server_url: str = DEFAULT_SERVER_URL,
    listing_url: str = DEFAULT_LISTING_URL,
    output_root: str | Path | None = None,
    base_doc_count: int = DEFAULT_BASE_DOC_COUNT,
    manifest_file: str | Path | None = None,
) -> dict:
    session = make_session()
    health = session.get(f"{server_url.rstrip('/')}/health", timeout=20)
    health.raise_for_status()

    if output_root is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = DEFAULT_OUTPUT_ROOT / timestamp
    else:
        output_dir = Path(output_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    if manifest_file:
        print(f"Loading base scenarios from manifest file: {manifest_file}")
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        scenarios = []
        for s in manifest_data.get("base_scenarios", []):
            scenarios.append(
                BaseScenario(
                    scenario_id=s["scenario_id"],
                    kind=s["kind"],
                    title=s["title"],
                    paragraphs=s.get("paragraphs") or [],
                    table_headers=s.get("table_headers") or [],
                    table_rows=s.get("table_rows") or [],
                    font_name=s.get("font_name", PRINT_FONT),
                    background=s.get("background", "white"),
                    foreground=s.get("foreground", "black"),
                )
            )
    else:
        scenarios = build_overall_scenarios(session, listing_url, base_doc_count=base_doc_count)

    transforms = ["clean", "rot90", "rot180", "rot270", "low_quality"]
    samples = build_samples(scenarios, output_dir, transforms)

    for sample in samples:
        ocr_text = call_local_ocr(session, server_url, Path(sample.image_path))
        accuracy, cer, distance, source_length, ocr_length = score_text_pair(sample.source_text, ocr_text)
        sample.ocr_text = ocr_text
        sample.accuracy = accuracy
        sample.cer = cer
        sample.edit_distance = distance
        sample.source_length = source_length
        sample.ocr_length = ocr_length

    manifest_path = write_manifest(output_dir, scenarios, samples, listing_url=listing_url)
    report_md, report_json = write_report(output_dir, samples)

    total_source = sum(sample.source_length for sample in samples)
    total_distance = sum(sample.edit_distance for sample in samples)
    weighted_accuracy = 1.0 if total_source == 0 else max(0.0, 1.0 - (total_distance / total_source))
    mean_accuracy = sum(sample.accuracy for sample in samples) / len(samples) if samples else 0.0

    print(f"Benchmark output: {output_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_md}")
    print(f"JSON: {report_json}")
    print(f"Weighted accuracy: {weighted_accuracy * 100:.2f}%")
    print(f"Mean sample accuracy: {mean_accuracy * 100:.2f}%")

    return {
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "report_path": str(report_md),
        "report_json_path": str(report_json),
        "weighted_accuracy": weighted_accuracy,
        "mean_accuracy": mean_accuracy,
        "sample_count": len(samples),
        "samples": [asdict(sample) for sample in samples],
        "scenarios": [asdict(scenario) for scenario in scenarios],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the overall Vietnamese OCR benchmark.")
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL, help="Local OCR server URL.")
    parser.add_argument("--listing-url", default=DEFAULT_LISTING_URL, help="Thư Viện Pháp Luật listing URL.")
    parser.add_argument("--output-dir", default=None, help="Output directory for images and reports.")
    parser.add_argument("--base-doc-count", type=int, default=DEFAULT_BASE_DOC_COUNT, help="How many legal docs to scrape.")
    parser.add_argument("--manifest-file", default=None, help="Use existing manifest file to avoid scraping.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_overall_benchmark(
        server_url=args.server_url,
        listing_url=args.listing_url,
        output_root=args.output_dir,
        base_doc_count=args.base_doc_count,
        manifest_file=args.manifest_file,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
