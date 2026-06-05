"""
Benchmark PaddleOCR against legal-document text from Thư Viện Pháp Luật.

The script scrapes a small set of legal documents that already have source text
available on the site, renders the extracted text into synthetic page images,
submits those images to the local OCR server, and compares OCR output against
the source text with a normalized character-level accuracy metric.

Usage:
    python tools/benchmark_thuvienphapluat_legal_ocr.py

Optional:
    python tools/benchmark_thuvienphapluat_legal_ocr.py --max-images 10
    python tools/benchmark_thuvienphapluat_legal_ocr.py --server-url http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from rapidfuzz.distance import Levenshtein


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LISTING_URL = "https://thuvienphapluat.vn/page/van-ban-tphcm.aspx"
DEFAULT_SERVER_URL = "http://127.0.0.1:5000"
DEFAULT_MAX_IMAGES = 10
DEFAULT_CANDIDATE_DOCS = 20
DEFAULT_PAGE_WIDTH = 1700
DEFAULT_PAGE_HEIGHT = 2200
DEFAULT_MARGIN_X = 90
DEFAULT_MARGIN_Y = 90
DEFAULT_FONT_SIZE = 26
DEFAULT_LINE_SPACING = 1.28


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass
class DocumentSource:
    url: str
    title: str
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class PageSample:
    sample_id: str
    document_url: str
    document_title: str
    page_index: int
    image_path: str
    source_text: str
    ocr_text: str = ""
    accuracy: float = 0.0
    cer: float = 0.0
    edit_distance: int = 0
    source_length: int = 0
    ocr_length: int = 0


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        }
    )
    return session


def fetch_listing_urls(session: requests.Session, listing_url: str, limit: int) -> list[str]:
    response = session.get(listing_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    urls: list[str] = []
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if "/van-ban/" not in href or not href.endswith(".aspx"):
            continue
        if href.startswith("/"):
            href = "https://thuvienphapluat.vn" + href
        if href not in urls:
            urls.append(href)
        if len(urls) >= limit:
            break
    return urls


def extract_document_title(soup: BeautifulSoup, fallback_url: str) -> str:
    title_candidates = [
        soup.find("h1"),
        soup.find("title"),
        soup.find("meta", attrs={"property": "og:title"}),
        soup.find("meta", attrs={"name": "title"}),
    ]

    for candidate in title_candidates:
        if candidate is None:
            continue
        if candidate.name == "meta":
            text = candidate.get("content") or ""
        else:
            text = candidate.get_text(" ", strip=True)
        text = normalize_whitespace(text)
        if text:
            return text

    slug = fallback_url.rstrip("/").split("/")[-1]
    return slug or "legal-document"


def extract_document_source(session: requests.Session, url: str) -> DocumentSource:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    title = extract_document_title(soup, url)

    content = soup.select_one("#divContentDoc")
    if content is None:
        paragraphs = [normalize_whitespace(p.get_text(" ", strip=True)) for p in soup.find_all("p")]
    else:
        paragraphs = [normalize_whitespace(p.get_text("\n", strip=True)) for p in content.find_all("p")]

    cleaned_paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    return DocumentSource(url=url, title=title, paragraphs=cleaned_paragraphs)


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()
    return text


def normalize_for_scoring(text: str) -> str:
    return normalize_whitespace(text)


def slugify(text: str, fallback: str = "document") -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:80] or fallback


def get_font(font_size: int) -> ImageFont.FreeTypeFont:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates = [
        windir / "Fonts" / "times.ttf",
        windir / "Fonts" / "arial.ttf",
        windir / "Fonts" / "tahoma.ttf",
        windir / "Fonts" / "calibri.ttf",
    ]
    for font_path in candidates:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), font_size)
    return ImageFont.load_default()


def measure_line_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    height = bbox[3] - bbox[1]
    return max(height + 8, 24)


def wrap_text(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = text.strip()
    if not text:
        return [""]

    words = text.split()
    lines: list[str] = []
    current = ""

    def text_width(candidate: str) -> float:
        if not candidate:
            return 0
        return draw.textlength(candidate, font=font)

    for word in words:
        candidate = word if not current else f"{current} {word}"
        if text_width(candidate) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        if text_width(word) <= max_width:
            current = word
            continue

        fragment = ""
        for char in word:
            candidate = fragment + char
            if text_width(candidate) <= max_width or not fragment:
                fragment = candidate
            else:
                lines.append(fragment)
                fragment = char
        current = fragment

    if current:
        lines.append(current)

    return lines or [""]


def paginate_paragraphs(
    paragraphs: Sequence[str],
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    page_width: int,
    page_height: int,
    margin_x: int,
    margin_y: int,
    line_spacing: float,
) -> list[list[str]]:
    max_width = page_width - (margin_x * 2)
    line_height = measure_line_height(draw, font)
    step = max(1, math.floor(line_height * line_spacing))
    blank_step = max(step // 2, 8)
    usable_bottom = page_height - margin_y

    pages: list[list[str]] = []
    current_lines: list[str] = []
    current_y = margin_y

    def flush_page() -> None:
        nonlocal current_lines, current_y
        if current_lines:
            pages.append(current_lines)
        current_lines = []
        current_y = margin_y

    for paragraph in paragraphs:
        normalized = paragraph.replace("\r", "").strip()
        if not normalized:
            if current_lines and current_y + blank_step > usable_bottom:
                flush_page()
            elif current_lines:
                current_lines.append("")
                current_y += blank_step
            continue

        for raw_line in normalized.split("\n"):
            wrapped_lines = wrap_text(raw_line, draw, font, max_width)
            for wrapped_line in wrapped_lines:
                if current_lines and current_y + step > usable_bottom:
                    flush_page()
                current_lines.append(wrapped_line)
                current_y += step

        if current_lines:
            if current_y + blank_step > usable_bottom:
                flush_page()
            else:
                current_lines.append("")
                current_y += blank_step

    if current_lines:
        pages.append(current_lines)

    return pages


def render_page_image(
    lines: Sequence[str],
    output_path: Path,
    page_width: int,
    page_height: int,
    margin_x: int,
    margin_y: int,
    line_spacing: float,
    font_size: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (page_width, page_height), "white")
    draw = ImageDraw.Draw(image)
    font = get_font(font_size)
    line_height = measure_line_height(draw, font)
    step = max(1, math.floor(line_height * line_spacing))

    y = margin_y
    for line in lines:
        draw.text((margin_x, y), line, fill="black", font=font)
        y += step

    image.save(output_path)


def build_page_samples(
    documents: Sequence[DocumentSource],
    output_dir: Path,
    max_images: int,
    page_width: int,
    page_height: int,
    margin_x: int,
    margin_y: int,
    line_spacing: float,
    font_size: int,
) -> list[PageSample]:
    dummy_image = Image.new("RGB", (page_width, page_height), "white")
    draw = ImageDraw.Draw(dummy_image)
    font = get_font(font_size)

    samples: list[PageSample] = []
    for doc_index, document in enumerate(documents, start=1):
        pages = paginate_paragraphs(
            document.paragraphs,
            draw=draw,
            font=font,
            page_width=page_width,
            page_height=page_height,
            margin_x=margin_x,
            margin_y=margin_y,
            line_spacing=line_spacing,
        )
        for page_index, page_lines in enumerate(pages, start=1):
            if len(samples) >= max_images:
                return samples

            image_name = f"{doc_index:02d}-{page_index:02d}-{slugify(document.title)}.png"
            image_path = output_dir / "images" / image_name
            render_page_image(
                page_lines,
                output_path=image_path,
                page_width=page_width,
                page_height=page_height,
                margin_x=margin_x,
                margin_y=margin_y,
                line_spacing=line_spacing,
                font_size=font_size,
            )
            sample_id = f"{doc_index:02d}-{page_index:02d}"
            source_text = "\n".join(line for line in page_lines if line is not None)
            samples.append(
                PageSample(
                    sample_id=sample_id,
                    document_url=document.url,
                    document_title=document.title,
                    page_index=page_index,
                    image_path=str(image_path),
                    source_text=source_text,
                    source_length=len(normalize_for_scoring(source_text)),
                )
            )

    return samples


def call_local_ocr(session: requests.Session, server_url: str, image_path: Path) -> str:
    with image_path.open("rb") as file_obj:
        files = {"files": (image_path.name, file_obj, "image/png")}
        response = session.post(f"{server_url.rstrip('/')}/ocr", files=files, timeout=180)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results") or []
    if not results:
        return ""
    first_result = results[0] or {}
    pages = first_result.get("pages") or []
    if not pages:
        return ""
    first_page = pages[0] or {}
    return first_page.get("text") or ""


def score_text_pair(source_text: str, ocr_text: str) -> tuple[float, float, int, int, int]:
    source_norm = normalize_for_scoring(source_text)
    ocr_norm = normalize_for_scoring(ocr_text)

    if not source_norm and not ocr_norm:
        return 1.0, 0.0, 0, 0, 0

    distance = Levenshtein.distance(source_norm, ocr_norm)
    denominator = max(len(source_norm), len(ocr_norm), 1)
    accuracy = max(0.0, 1.0 - (distance / denominator))
    cer = distance / max(len(source_norm), 1)
    return accuracy, cer, distance, len(source_norm), len(ocr_norm)


def write_manifest(
    output_dir: Path,
    documents: Sequence[DocumentSource],
    samples: Sequence[PageSample],
    listing_url: str,
) -> Path:
    manifest_path = output_dir / "manifest.json"
    manifest = {
        "listing_url": listing_url,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "documents": [
            {
                "url": doc.url,
                "title": doc.title,
                "paragraph_count": len(doc.paragraphs),
            }
            for doc in documents
        ],
        "samples": [asdict(sample) for sample in samples],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def write_report(output_dir: Path, samples: Sequence[PageSample]) -> Path:
    report_path = output_dir / "report.md"
    total_source = sum(sample.source_length for sample in samples)
    total_distance = sum(sample.edit_distance for sample in samples)
    total_ocr = sum(sample.ocr_length for sample in samples)

    weighted_accuracy = 1.0
    weighted_cer = 0.0
    if total_source > 0:
        weighted_accuracy = max(0.0, 1.0 - (total_distance / total_source))
        weighted_cer = total_distance / total_source

    mean_accuracy = sum(sample.accuracy for sample in samples) / len(samples) if samples else 0.0

    lines = [
        "# Thư Viện Pháp Luật OCR Benchmark",
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
        "## Samples",
        "",
        "| Sample | Document | Page | Accuracy | CER | Source len | OCR len |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for sample in samples:
        lines.append(
            f"| `{sample.sample_id}` | {sample.document_title} | {sample.page_index} | "
            f"{sample.accuracy * 100:.2f}% | {sample.cer * 100:.2f}% | "
            f"{sample.source_length} | {sample.ocr_length} |"
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run_benchmark(
    server_url: str = DEFAULT_SERVER_URL,
    listing_url: str = DEFAULT_LISTING_URL,
    max_images: int = DEFAULT_MAX_IMAGES,
    candidate_docs: int = DEFAULT_CANDIDATE_DOCS,
    output_dir: str | Path | None = None,
    page_width: int = DEFAULT_PAGE_WIDTH,
    page_height: int = DEFAULT_PAGE_HEIGHT,
    margin_x: int = DEFAULT_MARGIN_X,
    margin_y: int = DEFAULT_MARGIN_Y,
    line_spacing: float = DEFAULT_LINE_SPACING,
    font_size: int = DEFAULT_FONT_SIZE,
) -> dict:
    session = make_session()
    response = session.get(f"{server_url.rstrip('/')}/health", timeout=20)
    response.raise_for_status()

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_root = ROOT_DIR / "benchmark" / "thuvienphapluat_legal_ocr_runs" / timestamp
    else:
        output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    doc_urls = fetch_listing_urls(session, listing_url, candidate_docs)
    if not doc_urls:
        raise RuntimeError(f"No document URLs found at {listing_url}")

    documents: list[DocumentSource] = []
    for doc_url in doc_urls:
        try:
            documents.append(extract_document_source(session, doc_url))
        except Exception as exc:
            print(f"[warn] skip document {doc_url}: {exc}")

    if not documents:
        raise RuntimeError("No legal documents could be extracted from the listing page.")

    samples = build_page_samples(
        documents=documents,
        output_dir=output_root,
        max_images=max_images,
        page_width=page_width,
        page_height=page_height,
        margin_x=margin_x,
        margin_y=margin_y,
        line_spacing=line_spacing,
        font_size=font_size,
    )

    if not samples:
        raise RuntimeError("No page images were generated for the benchmark.")

    for sample in samples:
        ocr_text = call_local_ocr(session, server_url, Path(sample.image_path))
        accuracy, cer, distance, source_length, ocr_length = score_text_pair(sample.source_text, ocr_text)
        sample.ocr_text = ocr_text
        sample.accuracy = accuracy
        sample.cer = cer
        sample.edit_distance = distance
        sample.source_length = source_length
        sample.ocr_length = ocr_length

    manifest_path = write_manifest(output_root, documents, samples, listing_url=listing_url)
    report_path = write_report(output_root, samples)
    report_json_path = output_root / "report.json"
    report_json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "server_url": server_url,
                "listing_url": listing_url,
                "samples": [asdict(sample) for sample in samples],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    total_source = sum(sample.source_length for sample in samples)
    total_distance = sum(sample.edit_distance for sample in samples)
    weighted_accuracy = 1.0 if total_source == 0 else max(0.0, 1.0 - (total_distance / total_source))
    mean_accuracy = sum(sample.accuracy for sample in samples) / len(samples)
    print(f"Benchmark output: {output_root}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")
    print(f"JSON: {report_json_path}")
    print(f"Weighted accuracy: {weighted_accuracy * 100:.2f}%")
    print(f"Mean sample accuracy: {mean_accuracy * 100:.2f}%")

    return {
        "output_dir": str(output_root),
        "manifest_path": str(manifest_path),
        "report_path": str(report_path),
        "report_json_path": str(report_json_path),
        "weighted_accuracy": weighted_accuracy,
        "mean_accuracy": mean_accuracy,
        "sample_count": len(samples),
        "samples": [asdict(sample) for sample in samples],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark OCR against Thư Viện Pháp Luật legal text.")
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL, help="Local OCR server URL.")
    parser.add_argument("--listing-url", default=DEFAULT_LISTING_URL, help="Thư Viện Pháp Luật listing page URL.")
    parser.add_argument("--max-images", type=int, default=DEFAULT_MAX_IMAGES, help="Maximum rendered page images.")
    parser.add_argument("--candidate-docs", type=int, default=DEFAULT_CANDIDATE_DOCS, help="How many legal docs to inspect.")
    parser.add_argument("--output-dir", default=None, help="Output directory for images and reports.")
    parser.add_argument("--page-width", type=int, default=DEFAULT_PAGE_WIDTH, help="Synthetic image width.")
    parser.add_argument("--page-height", type=int, default=DEFAULT_PAGE_HEIGHT, help="Synthetic image height.")
    parser.add_argument("--margin-x", type=int, default=DEFAULT_MARGIN_X, help="Horizontal margin in pixels.")
    parser.add_argument("--margin-y", type=int, default=DEFAULT_MARGIN_Y, help="Vertical margin in pixels.")
    parser.add_argument("--line-spacing", type=float, default=DEFAULT_LINE_SPACING, help="Line spacing multiplier.")
    parser.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE, help="Font size in pixels.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_benchmark(
        server_url=args.server_url,
        listing_url=args.listing_url,
        max_images=args.max_images,
        candidate_docs=args.candidate_docs,
        output_dir=args.output_dir,
        page_width=args.page_width,
        page_height=args.page_height,
        margin_x=args.margin_x,
        margin_y=args.margin_y,
        line_spacing=args.line_spacing,
        font_size=args.font_size,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
