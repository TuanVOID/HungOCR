"""Shared helpers for local OCR benchmarks."""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from rapidfuzz.distance import Levenshtein


DEFAULT_LISTING_URL = "https://thuvienphapluat.vn/page/van-ban-tphcm.aspx"
DEFAULT_SERVER_URL = "http://127.0.0.1:5000"
DEFAULT_CANDIDATE_DOCS = 20
DEFAULT_PAGE_WIDTH = 1700
DEFAULT_PAGE_HEIGHT = 2200
DEFAULT_MARGIN_X = 90
DEFAULT_MARGIN_Y = 90
DEFAULT_FONT_SIZE = 26
DEFAULT_LINE_SPACING = 1.28


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
    paragraphs,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    page_width: int,
    page_height: int,
    margin_x: int,
    margin_y: int,
    line_spacing: float,
) -> list[list[str]]:
    max_width = page_width - (margin_x * 2)
    step = max(1, math.floor(measure_line_height(draw, font) * line_spacing))
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
    lines,
    output_path: Path,
    page_width: int,
    page_height: int,
    margin_x: int,
    margin_y: int,
    line_spacing: float,
    font_size: int,
) -> None:
    image = Image.new("RGB", (page_width, page_height), "white")
    draw = ImageDraw.Draw(image)
    font = get_font(font_size)
    step = max(1, math.floor(measure_line_height(draw, font) * line_spacing))

    y = margin_y
    for line in lines:
        draw.text((margin_x, y), line, fill="black", font=font)
        y += step

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def build_page_samples(
    documents,
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
