"""Run the official olmOCR pipeline with a legal-document preservation prompt."""

import base64
import os
import re
import unicodedata
from argparse import Namespace
from contextvars import ContextVar
from dataclasses import replace
from difflib import SequenceMatcher
from importlib.metadata import version
from io import BytesIO

import pypdfium2 as pdfium
from olmocr import pipeline
from olmocr.prompts import build_no_anchoring_v4_yaml_prompt
from PIL import Image

HEADER_PASS: ContextVar[bool] = ContextVar("header_pass", default=False)
SECOND_LOOK: ContextVar[bool] = ContextVar("second_look", default=False)
ORIGINAL_QUERY = pipeline.build_page_query
ORIGINAL_PAGE = pipeline.process_page
# The document-type title and the "Căn cứ" preamble both end the opening
# identification block; the preamble repeats authority names.
TITLE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:LUẬT|BỘ LUẬT|NGHỊ QUYẾT|NGHỊ ĐỊNH|"
    r"QUYẾT ĐỊNH|THÔNG TƯ|CHỈ THỊ|PHÁP LỆNH|CÔNG VĂN|THÔNG BÁO|"
    r"BÁO CÁO|KẾ HOẠCH|TỜ TRÌNH)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
PREAMBLE = re.compile(r"^\s*(?:[*_]+\s*)?Căn cứ", re.MULTILINE | re.IGNORECASE)
TABLE = re.compile(r"<table>.*?</table>", re.S)
ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
# Whole first-column headers that name a row identifier rather than content:
# numbering (STT, TT, Số TT, Số thứ tự, Điều, Mục, ID) or a code family (Mã
# hàng, Mã số, Số hiệu, Ký hiệu, ...).
ID_HEADER = re.compile(
    r"(?:stt|tt|số\s*tt|số\s*thứ\s*tự|thứ\s*tự|số|điều|mục|id)\.?"
    r"|(?:mã|số\s*hiệu|ký\s*hiệu|số\s*ký\s*hiệu)\b.*",
    re.IGNORECASE,
)
# Identifier shapes seen in first columns of real documents.
ID_SHAPES = {
    "document": r"\d+/\d{4}/[\w-]+",  # 137/2016/NĐ-CP
    "number": r"\d+(?:[./-]\d+)*\.?",  # 1  1.  1.2  0101.21.00
    "roman": r"[IVXLC]+\.?",  # I  II.  IV
    "letter": r"[a-zđ]\)",  # a)  đ)
    "code": r"[A-ZĐ]{1,6}[-.]?\d+[\w.-]*",  # QHHH-01  KTX-01  A01
}
ROTATIONS = {
    90: Image.Transpose.ROTATE_90,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_270,
}


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
    # Keep each page request within the locally tuned 6.5k vLLM context window.
    # 4k output tokens is ample for a dense legal page and leaves room for the
    # rendered image and preservation prompt.
    query["max_tokens"] = int(os.getenv("OLMOCR_MAX_OUTPUT_TOKENS", "4096"))
    if not HEADER_PASS.get():
        if SECOND_LOOK.get():
            query["messages"][0]["content"][1]["image_url"]["url"] = (
                "data:image/png;base64,"
                + rerender_page(
                    local_pdf_path, page, target_longest_image_dim, image_rotation
                )
            )
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
    result = await recover_table_ids(
        result, args, worker_id, pdf_orig_path, pdf_local_path, page_num
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
    title = TITLE.search(text)
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
    body = merge_opening_block(text, result.response.natural_text or "")
    pipeline.logger.info(
        "Recovered opening identification block for %s: %s", pdf_orig_path, text
    )
    return replace(
        result,
        response=replace(result.response, natural_text=body),
        input_tokens=result.input_tokens + header.input_tokens,
        output_tokens=result.output_tokens + header.output_tokens,
    )


async def recover_table_ids(
    result: pipeline.PageResult,
    args: Namespace,
    worker_id: int,
    pdf_orig_path: str,
    pdf_local_path: str,
    page_num: int,
) -> pipeline.PageResult:
    """Take a second look at a page whose identifier column came back empty.

    On some scanned tables the model unpredictably drops the identifier column
    (STT, Mã hàng, Ký hiệu, ...) or merges it into the next cell. A differently
    rasterised render kept the column in 10 of 12 trials on such a page, so the
    page is read up to twice more. A reading is only taken over if it fills more
    identifiers and its other text matches the first reading closely.
    """
    text = split_merged_ids(result.response.natural_text or "")
    best = replace(result, response=replace(result.response, natural_text=text))
    if best.is_fallback or not best.is_valid or not missing_ids(text):
        return best
    first_words = _content_words(text)
    input_tokens, output_tokens = best.input_tokens, best.output_tokens
    for _ in range(2):
        token = SECOND_LOOK.set(True)
        try:
            retry = await ORIGINAL_PAGE(
                args, worker_id, pdf_orig_path, pdf_local_path, page_num
            )
        finally:
            SECOND_LOOK.reset(token)
        input_tokens += retry.input_tokens
        output_tokens += retry.output_tokens
        retry_text = split_merged_ids(retry.response.natural_text or "")
        if (
            not retry.is_fallback
            and retry.is_valid
            and id_rows(retry_text)[1] > id_rows(best.response.natural_text)[1]
            and SequenceMatcher(
                a=first_words, b=_content_words(retry_text), autojunk=False
            ).ratio()
            >= 0.8
        ):
            best = replace(
                retry, response=replace(retry.response, natural_text=retry_text)
            )
        if not missing_ids(best.response.natural_text):
            break
    pipeline.logger.info(
        "Second look at %s page %d for an empty identifier column: %s",
        pdf_orig_path,
        page_num,
        "still empty" if missing_ids(best.response.natural_text) else "recovered",
    )
    return replace(best, input_tokens=input_tokens, output_tokens=output_tokens)


def rerender_page(pdf_path: str, page: int, longest: int, rotation: int) -> str:
    """Render via pdfium at 200 dpi grey and JPEG instead of poppler's direct render."""
    document = pdfium.PdfDocument(pdf_path)
    try:
        grey = document[page - 1].render(scale=200 / 72).to_pil().convert("L")
    finally:
        document.close()
    jpeg = BytesIO()
    grey.convert("RGB").save(jpeg, format="JPEG", quality=75)
    with Image.open(BytesIO(jpeg.getvalue())) as image:
        scale = longest / max(image.size)
        size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(size, Image.LANCZOS)
    if rotation:
        image = image.transpose(ROTATIONS[rotation])
    png = BytesIO()
    image.save(png, format="PNG")
    return base64.b64encode(png.getvalue()).decode("ascii")


def _cells(row: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", cell).strip() for cell in CELL.findall(row)]


def _shape(token: str) -> str | None:
    for name, pattern in ID_SHAPES.items():
        if re.fullmatch(pattern, token):
            return name
    return None


def _lead(cell: str) -> str | None:
    """Identifier shape of a cell's first word when more text follows it."""
    words = cell.split(None, 1)
    return _shape(words[0]) if len(words) == 2 else None


def _id_tables(text: str) -> list[str]:
    """Tables whose first header cell names a row identifier column."""
    tables = []
    for table in TABLE.findall(text):
        first = ROW.search(table)
        head = _cells(first.group(1)) if first else []
        if head and ID_HEADER.fullmatch(head[0]):
            tables.append(table)
    return tables


def split_merged_ids(text: str) -> str:
    """Move identifiers written at the start of the second cell back to the first.

    Only when most rows with an empty first cell start with identifiers of one
    shape, and that shape matches the identifiers already in the column, so an
    isolated number that belongs to the text is never moved.
    """
    for table in _id_tables(text):
        rows = [_cells(r) for r in ROW.findall(table) if "<td" in r]
        rows = [c for c in rows if len(c) >= 2]
        empty = [c for c in rows if not c[0] and c[1]]
        known = {_shape(c[0].split()[0]) for c in rows if c[0]} - {None}
        leads = [s for s in (_lead(c[1]) for c in empty) if s]
        if not leads:
            continue
        shape = max(set(leads), key=leads.count)
        if leads.count(shape) < max(2, len(empty) / 2) or (known and shape not in known):
            continue
        merged = re.compile(
            r"<td>\s*</td>(\s*)<td>(\s*(?:<b>)?)(" + ID_SHAPES[shape] + r")\s+(?=\S)"
        )
        fixed = ROW.sub(
            lambda m: "<tr>" + merged.sub(r"<td>\3</td>\1<td>\2", m.group(1), 1) + "</tr>",
            table,
        )
        text = text.replace(table, fixed)
    return text


def id_rows(text: str) -> tuple[int, int]:
    """Data rows of identifier-column tables, and how many have an identifier.

    A data row has content after its description (or in its only other cell),
    so group headings without values are not counted.
    """
    rows = filled = 0
    for table in _id_tables(text):
        for row in ROW.findall(table):
            cells = _cells(row)
            if "<td" in row and len(cells) >= 2 and any(cells[2:] or cells[1:]):
                rows += 1
                filled += bool(cells[0])
    return rows, filled


def missing_ids(text: str) -> bool:
    """True when an identifier column is (almost) entirely empty."""
    for table in _id_tables(text):
        rows, filled = id_rows(table)
        if rows >= 4 and filled <= rows * 0.2:
            return True
    return False


def _content_words(text: str) -> list[str]:
    """Words outside the first column of each table row, to compare readings."""

    def row_words(match: re.Match) -> str:
        cells = _cells(match.group(1))[1:]
        if cells and _lead(cells[0]):
            cells[0] = cells[0].split(None, 1)[1]
        return " " + " ".join(cells) + " "

    return re.sub(r"<[^>]+>", " ", ROW.sub(row_words, text)).split()


def _comparable(text: str) -> str:
    # The body pass may join both identification columns on one line or wrap
    # them in markdown, so compare words rather than line layout.
    text = unicodedata.normalize("NFC", re.sub(r"[*#|]", " ", text))
    return " ".join(text.split()).casefold()


def merge_opening_block(header: str, body: str) -> str:
    """Prepend only the header lines that the body's opening does not contain."""
    ends = [m.start() for m in (TITLE.search(body), PREAMBLE.search(body)) if m]
    opening = _comparable(body[: min([1200, *ends])])
    lines = [
        line
        for line in header.splitlines()
        if line.strip() and _comparable(line) not in opening
    ]
    if not lines:
        return body
    return "\n".join(lines) + "\n\n" + body


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
        "Profile: legal-preserve-v3 (official body OCR + opening-block crop"
        " + identifier-column second look)",
        flush=True,
    )
    pipeline.cli_main()


if __name__ == "__main__":
    main()
