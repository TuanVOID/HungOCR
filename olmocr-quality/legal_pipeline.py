"""Run the official olmOCR pipeline with a legal-document preservation prompt."""

import base64
import re
from argparse import Namespace
from contextvars import ContextVar
from dataclasses import replace
from importlib.metadata import version
from io import BytesIO

from olmocr import pipeline
from olmocr.prompts import build_no_anchoring_v4_yaml_prompt
from PIL import Image

HEADER_PASS: ContextVar[bool] = ContextVar("header_pass", default=False)
ORIGINAL_QUERY = pipeline.build_page_query
ORIGINAL_PAGE = pipeline.process_page


async def build_query(
    local_pdf_path: str,
    page: int,
    target_longest_image_dim: int,
    image_rotation: int = 0,
    model_name: str = "olmocr",
) -> dict:
    query = await ORIGINAL_QUERY(
        local_pdf_path, page, target_longest_image_dim, image_rotation, model_name
    )
    if not HEADER_PASS.get():
        return query
    content = query["messages"][0]["content"]
    # Render first, then crop, so the identifier is not downsampled with the full page.
    image_data = content[1]["image_url"]["url"].split(",", 1)[1]
    with Image.open(BytesIO(base64.b64decode(image_data))) as image:
        with image.crop((0, 0, image.width, round(image.height * 0.24))) as crop:
            buffer = BytesIO()
            crop.save(buffer, format="PNG")
    content[1]["image_url"]["url"] = "data:image/png;base64," + base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")
    content[0]["text"] = build_legal_prompt() + (
        "\nThis image is ONLY the opening identification area of a page. "
        "Transcribe the issuing authority, document number, national heading, "
        "motto and issuance date exactly as visible, in both columns. "
        "Do not transcribe the document title or body below this identification block. "
        "If no such identification block is visible, return empty natural text. "
        "Do not classify the identification block as a header to omit."
    )
    return query


async def process_page(
    args: Namespace,
    worker_id: int,
    pdf_orig_path: str,
    pdf_local_path: str,
    page_num: int,
) -> pipeline.PageResult:
    result = await ORIGINAL_PAGE(
        args, worker_id, pdf_orig_path, pdf_local_path, page_num
    )
    if page_num != 1 or not result.is_valid:
        return result
    token = HEADER_PASS.set(True)
    try:
        header = await ORIGINAL_PAGE(args, worker_id, pdf_orig_path, pdf_local_path, 1)
    finally:
        HEADER_PASS.reset(token)
    text = header.response.natural_text or ""
    # A crop can overlap the title. Never prepend that title/body a second time,
    # even when the model ignores the identification-only instruction.
    title = re.search(
        r"^\s*(?:#{1,6}\s*)?(?:LUẬT|BỘ LUẬT|NGHỊ QUYẾT|NGHỊ ĐỊNH|"
        r"QUYẾT ĐỊNH|THÔNG TƯ|CHỈ THỊ|PHÁP LỆNH|CÔNG VĂN|THÔNG BÁO|"
        r"BÁO CÁO|KẾ HOẠCH|TỜ TRÌNH)\s*$",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    if title is not None:
        text = text[: title.start()].strip()
    # Require evidence of a document identification block, not ordinary body text.
    if not header.is_valid or not re.search(
        r"\d+[/-]\d{4}[/-]|CỘNG H[ÒO]A|Độc lập", text, re.IGNORECASE
    ):
        pipeline.logger.warning(
            "No reliable opening identification block recovered for %s", pdf_orig_path
        )
        return result
    body = result.response.natural_text or ""
    existing_lines = {line.strip() for line in body[:1200].splitlines()}
    lines = [
        line
        for line in text.splitlines()
        if line.strip() and line.strip() not in existing_lines
    ]
    if lines:
        body = "\n".join(lines) + "\n\n" + body
    pipeline.logger.info(
        "Recovered opening identification block for %s: %s", pdf_orig_path, text
    )
    return replace(
        result,
        response=replace(result.response, natural_text=body),
        input_tokens=result.input_tokens + header.input_tokens,
        output_tokens=result.output_tokens + header.output_tokens,
    )


def build_legal_prompt() -> str:
    """Keep the official response contract while preserving document identity."""
    return build_no_anchoring_v4_yaml_prompt() + (
        "\nTranscribe the complete visible legal or administrative document, "
        "including its opening identification block before the title and body. "
        "Do not omit text just because it is near the top of the page. "
        "Preserve the issuing authority (co quan ban hanh), national heading and "
        "motto (quoc hieu, tieu ngu), document number/reference (so, ky hieu), "
        "place and date of issue, and any signature block when they are visible. "
        "These are essential document content, not disposable running headers. "
        "Read both columns of an opening identification block; keep each column's "
        "lines together, left block then right block, followed by the title and body. "
        "Copy document identifiers exactly, including digits, slashes, hyphens and "
        "letter case. Preserve Vietnamese diacritics. Never infer missing numbers, "
        "dates or authority names, and never add a standard heading from memory. "
        "Only omit unrelated publisher advertising, website watermarks and scanning "
        "artifacts. Retain all substantive body text, tables and footnotes. "
        "Keep the required YAML front matter, then output the transcription.\n"
    )


def main() -> None:
    # Adapt the installed pipeline's page/query callbacks only in this process.
    # Fail on upgrades until the integration and output parser are rechecked.
    if version("olmocr") != "0.4.27":
        raise RuntimeError(
            "Revalidate legal_pipeline.py for the installed olmocr version."
        )
    pipeline.build_page_query = build_query
    pipeline.process_page = process_page
    print(
        "Profile: legal-preserve-v2 (official body OCR + opening-block crop)",
        flush=True,
    )
    pipeline.cli_main()


if __name__ == "__main__":
    main()
