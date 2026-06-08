import os
import json
import re
import sys
import tempfile
import shutil
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO

from dotenv import load_dotenv
load_dotenv() # Load environmental variables from .env

import numpy as np
from PIL import Image
from flask import Flask, request, jsonify, render_template, send_file
import pypdfium2 as pdfium
import requests
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from werkzeug.utils import secure_filename

# Ensure UTF-8 printing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB

ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.docx'}
STORAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "Storage"))
STORAGE_INPUT_ROOT = os.path.join(STORAGE_ROOT, "input")
STORAGE_OUTPUT_ROOT = os.path.join(STORAGE_ROOT, "output")

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "Tổng dung lượng file gửi lên vượt quá giới hạn (tối đa 15MB)."}), 413

def get_int_env(name, default):
    raw_value = os.getenv(name, str(default))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


STORAGE_RETENTION_DAYS = get_int_env("STORAGE_RETENTION_DAYS", 7)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.0.6:11434").rstrip("/")
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "qwen3.5:4B")
LLM_CHUNK_MAX_CHARS = get_int_env("LLM_CHUNK_MAX_CHARS", 6000)
LLM_INPUT_MAX_CHARS = get_int_env("LLM_INPUT_MAX_CHARS", 6000)
LLM_OUTPUT_MAX_TOKENS = get_int_env("LLM_OUTPUT_MAX_TOKENS", 6000)
MAX_UPLOAD_FILE_SIZE_BYTES = get_int_env("MAX_UPLOAD_FILE_SIZE_BYTES", 10 * 1024 * 1024)
MAX_PDF_PAGES = get_int_env("MAX_PDF_PAGES", 20)
MAX_IMAGE_PIXELS = get_int_env("MAX_IMAGE_PIXELS", 20_000_000)
MAX_IMAGE_EDGE = get_int_env("MAX_IMAGE_EDGE", 12000)
MAX_DOCX_TEXT_CHARS = get_int_env("MAX_DOCX_TEXT_CHARS", 30000)

# Global model placeholders
detectors = {}
recognizer = None
local_weights = 'C:/Indti/project-gitclone/deepdoc_vietocr/vietocr/weight/vgg_seq2seq.pth'

OCR_IMPORT_TYPES = {
    "clear": {
        "label": "Rõ ràng (nhanh)",
        "det_db_score_mode": "fast",
    },
    "complex": {
        "label": "Phức tạp (chậm)",
        "det_db_score_mode": "slow",
    },
}


def normalize_import_type(raw_value):
    value = str(raw_value or "clear").strip().lower()
    if value not in OCR_IMPORT_TYPES:
        return "clear"
    return value


def ensure_storage_dirs():
    os.makedirs(STORAGE_INPUT_ROOT, exist_ok=True)
    os.makedirs(STORAGE_OUTPUT_ROOT, exist_ok=True)


def build_storage_paths(raw_filename):
    now = datetime.now()
    date_folder = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%H-%M-%S")
    unique_id = uuid.uuid4().hex[:6]
    safe_name = secure_filename(raw_filename or "") or "file"
    stem, ext = os.path.splitext(safe_name)
    base_name = f"{timestamp}_{unique_id}_{stem}"
    input_dir = os.path.join(STORAGE_INPUT_ROOT, date_folder)
    output_dir = os.path.join(STORAGE_OUTPUT_ROOT, date_folder)
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    return {
        "input_path": os.path.join(input_dir, base_name + ext),
        "output_path": os.path.join(output_dir, base_name + ".json"),
        "saved_at": now,
    }


def build_ocr_output_payload(filename, import_type, layout_preserve, pages_text, saved_at, status="success", message=""):
    full_text = "\n\n".join(
        str(page.get("text", "")).strip()
        for page in pages_text
        if str(page.get("text", "")).strip()
    ).strip()
    return {
        "filename": filename,
        "saved_at": saved_at.isoformat(timespec="seconds"),
        "status": status,
        "message": message,
        "import_type": import_type,
        "layout_preserve": layout_preserve,
        "pages": pages_text,
        "text": full_text,
    }


def write_ocr_output_json(output_path, payload):
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)


def cleanup_storage_older_than(retention_days):
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    weeks_to_keep = max(2, (retention_days + 6) // 7)
    cutoff_date = current_week_start - timedelta(days=7 * (weeks_to_keep - 1))

    for root_dir in (STORAGE_INPUT_ROOT, STORAGE_OUTPUT_ROOT):
        if not os.path.exists(root_dir):
            continue

        for folder_name in os.listdir(root_dir):
            folder_path = os.path.join(root_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue
            try:
                folder_date = datetime.strptime(folder_name, "%Y-%m-%d").date()
            except ValueError:
                continue
            # Keep the current week plus the most recent completed week.
            if folder_date < cutoff_date:
                try:
                    shutil.rmtree(folder_path)
                except Exception as cleanup_error:
                    print(f"Warning: could not remove stored folder {folder_path}: {cleanup_error}")


def get_detector(import_type="clear"):
    import_type = normalize_import_type(import_type)

    if import_type in detectors:
        return detectors[import_type]

    mode_config = OCR_IMPORT_TYPES[import_type]
    print(f"Initializing detector for import type '{import_type}'...")

    from paddleocr import PaddleOCR

    detector_kwargs = dict(
        lang="vi",
        device="cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
    )

    try:
        detector = PaddleOCR(
            **detector_kwargs,
            det_db_score_mode=mode_config["det_db_score_mode"],
        )
    except (TypeError, ValueError):
        print(
            "Warning: PaddleOCR does not accept det_db_score_mode in this environment; "
            "falling back to default detector settings."
        )
        detector = PaddleOCR(**detector_kwargs)

    detectors[import_type] = detector
    return detector

def init_models():
    global recognizer
    print("Initializing models globally...")
    from vietocr.tool.predictor import Predictor
    from vietocr.tool.config import Cfg

    # Initialize the default OCR detector so the first request stays responsive.
    get_detector("clear")

    # Initialize VietOCR recognizer (VGG Seq2Seq model)
    config = Cfg.load_config_from_name('vgg_seq2seq')
    config['device'] = 'cpu'
    config['predictor']['beamsearch'] = False
    if os.path.exists(local_weights):
        config['weights'] = local_weights
        print(f"Loaded local weights from: {local_weights}")
    else:
        print("Warning: Local weights not found. VietOCR will download from internet if online.")
    recognizer = Predictor(config)
    print("Models initialized successfully!")

# Initialize on startup
ensure_storage_dirs()
cleanup_storage_older_than(STORAGE_RETENTION_DAYS)
init_models()

def crop_box(image, box, padding=3):
    try:
        pts = np.array(box, dtype=np.float32)
        min_x = np.min(pts[:, 0])
        max_x = np.max(pts[:, 0])
        min_y = np.min(pts[:, 1])
        max_y = np.max(pts[:, 1])

        left = max(0, int(min_x - padding))
        top = max(0, int(min_y - padding))
        right = min(image.width, int(max_x + padding))
        bottom = min(image.height, int(max_y + padding))

        if left >= right or top >= bottom:
            return None

        return image.crop((left, top, right, bottom))
    except Exception:
        return None

def sort_lines(lines_data, y_tolerance=12.0):
    if not lines_data:
        return []
        
    processed = []
    for idx, item in enumerate(lines_data):
        box = item["box"]
        pts = np.array(box, dtype=np.float32)
        min_x = float(np.min(pts[:, 0]))
        max_x = float(np.max(pts[:, 0]))
        min_y = float(np.min(pts[:, 1]))
        max_y = float(np.max(pts[:, 1]))
        center_y = (min_y + max_y) / 2.0
        processed.append({
            "item": item,
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "center_y": center_y,
            "height": max_y - min_y
        })
        
    processed.sort(key=lambda x: x["min_y"])
    
    lines = []
    for p in processed:
        added = False
        for line in lines:
            avg_center_y = sum(x["center_y"] for x in line) / len(line)
            avg_height = sum(x["height"] for x in line) / len(line)
            tolerance = max(y_tolerance, avg_height * 0.5)
            if abs(p["center_y"] - avg_center_y) < tolerance:
                line.append(p)
                added = True
                break
        if not added:
            lines.append([p])
            
    for line in lines:
        line.sort(key=lambda x: x["min_x"])
        
    lines.sort(key=lambda line: sum(x["center_y"] for x in line) / len(line))
    
    sorted_items = []
    for line in lines:
        for x in line:
            sorted_items.append(x["item"])
            
    return sorted_items


def format_layout_preserving(lines_data, y_tolerance=12.0, target_char_width=100):
    if not lines_data:
        return ""
        
    processed = []
    for idx, item in enumerate(lines_data):
        box = item["box"]
        pts = np.array(box, dtype=np.float32)
        min_x = float(np.min(pts[:, 0]))
        max_x = float(np.max(pts[:, 0]))
        min_y = float(np.min(pts[:, 1]))
        max_y = float(np.max(pts[:, 1]))
        center_y = (min_y + max_y) / 2.0
        processed.append({
            "item": item,
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "center_y": center_y,
            "height": max_y - min_y
        })
        
    processed.sort(key=lambda x: x["min_y"])
    
    lines = []
    for p in processed:
        added = False
        for line in lines:
            avg_center_y = sum(x["center_y"] for x in line) / len(line)
            avg_height = sum(x["height"] for x in line) / len(line)
            tolerance = max(y_tolerance, avg_height * 0.5)
            if abs(p["center_y"] - avg_center_y) < tolerance:
                line.append(p)
                added = True
                break
        if not added:
            lines.append([p])
            
    for line in lines:
        line.sort(key=lambda x: x["min_x"])
        
    lines.sort(key=lambda line: sum(x["center_y"] for x in line) / len(line))
    
    # Calculate global page horizontal bounds
    page_min_x = min(p["min_x"] for p in processed)
    page_max_x = max(p["max_x"] for p in processed)
    page_width = page_max_x - page_min_x
    if page_width <= 0:
        page_width = 1.0

    reconstructed_lines = []
    for line in lines:
        line_chars = [" "] * target_char_width
        last_end_idx = 0
        for idx, p in enumerate(line):
            # Map start X to character index
            start_col = int(((p["min_x"] - page_min_x) / page_width) * (target_char_width - 1))
            text = p["item"]["text"]
            
            # Avoid overlap with previous text blocks on the same line
            if start_col < last_end_idx:
                start_col = last_end_idx
                # Insert a space if it is not overlapping physically
                if idx > 0 and p["min_x"] > line[idx - 1]["max_x"] + 3:
                    start_col += 1
            
            # Write characters to line buffer
            for i, char in enumerate(text):
                col_idx = start_col + i
                if col_idx < len(line_chars):
                    line_chars[col_idx] = char
                else:
                    line_chars.append(char)
            
            last_end_idx = start_col + len(text)
            
        reconstructed_lines.append("".join(line_chars).rstrip())
        
    return "\n".join(reconstructed_lines)


def sanitize_sheet_title(title, fallback="Sheet"):
    cleaned = re.sub(r"[\[\]\:\*\?\/\\]", " ", str(title or "")).strip()
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        cleaned = fallback
    return cleaned[:31]


def unique_sheet_title(workbook, desired_title, fallback="Sheet"):
    base_title = sanitize_sheet_title(desired_title, fallback=fallback)
    if base_title not in workbook.sheetnames:
        return base_title

    suffix_index = 2
    while True:
        suffix = f" {suffix_index}"
        truncated = base_title[: max(0, 31 - len(suffix))].rstrip()
        candidate = f"{truncated}{suffix}" if truncated else f"{fallback}{suffix}"
        if candidate not in workbook.sheetnames:
            return candidate
        suffix_index += 1


def normalize_cell_value(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        normalized_items = [normalize_cell_value(item) for item in value]
        return "; ".join(item for item in normalized_items if item)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    
    val_str = str(value)
    # Prevent Excel/CSV Formula Injection: if value starts with =, +, -, @, prepend a single quote '
    if val_str and val_str[0] in ('=', '+', '-', '@'):
        try:
            # Check if it is a simple negative number to avoid ruining numbers
            float(val_str)
        except ValueError:
            val_str = "'" + val_str
    return val_str

def check_file_signature(file_stream, extension):
    header = file_stream.read(16)
    file_stream.seek(0) # Reset stream pointer
    if not header:
        return False
    
    ext = extension.lower()
    if ext == '.pdf':
        return header.startswith(b'%PDF')
    elif ext == '.png':
        return header.startswith(b'\x89PNG')
    elif ext in ('.jpg', '.jpeg'):
        return header.startswith(b'\xff\xd8')
    elif ext == '.bmp':
        return header.startswith(b'BM')
    elif ext == '.webp':
        return header.startswith(b'RIFF') and b'WEBP' in header
    elif ext in ('.tiff', '.tif'):
        return header.startswith(b'II*\x00') or header.startswith(b'MM\x00*')
    elif ext == '.docx':
        return header.startswith(b'PK\x03\x04')
    return False


def preflight_input_file(temp_path, filename):
    lower_name = (filename or "").lower()

    if lower_name.endswith(".pdf"):
        pdf_doc = pdfium.PdfDocument(temp_path)
        try:
            num_pages = len(pdf_doc)
            if num_pages > MAX_PDF_PAGES:
                raise ValueError(
                    f"Tài liệu PDF vượt quá giới hạn số trang cho phép (tối đa {MAX_PDF_PAGES} trang, file này có {num_pages} trang)."
                )
        finally:
            try:
                close_fn = getattr(pdf_doc, "close", None)
                if callable(close_fn):
                    close_fn()
            except Exception:
                pass
        return

    if lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif")):
        with Image.open(temp_path) as img:
            width, height = img.size
            if width <= 0 or height <= 0:
                raise ValueError("Ảnh đầu vào không hợp lệ.")
            pixel_count = width * height
            if pixel_count > MAX_IMAGE_PIXELS:
                raise ValueError(
                    f"Ảnh vượt quá giới hạn độ phân giải cho phép (tối đa {MAX_IMAGE_PIXELS:,} pixel, ảnh này có {pixel_count:,} pixel)."
                )
            if max(width, height) > MAX_IMAGE_EDGE:
                raise ValueError(
                    f"Ảnh vượt quá giới hạn kích thước cạnh cho phép (tối đa {MAX_IMAGE_EDGE} px mỗi cạnh, ảnh này là {width}x{height} px)."
                )


def autofit_worksheet(sheet, max_width=80):
    for column_cells in sheet.columns:
        column_letter = column_cells[0].column_letter
        longest = 0
        for cell in column_cells:
            cell_value = normalize_cell_value(cell.value)
            if cell_value:
                longest = max(longest, max(len(line) for line in cell_value.splitlines()))
        sheet.column_dimensions[column_letter].width = min(max(longest + 2, 12), max_width)


def build_raw_ocr_sheet(workbook, response_results):
    sheet = workbook.create_sheet(title=unique_sheet_title(workbook, "Raw OCR"))
    headers = ["File", "Page", "Status", "Text", "Message"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for file_result in response_results:
        filename = file_result.get("filename", "")
        status = file_result.get("status", "")
        pages = file_result.get("pages", [])

        if isinstance(pages, list) and pages:
            for page in pages:
                sheet.append([
                    filename,
                    page.get("page_number", ""),
                    status,
                    page.get("text", ""),
                    "",
                ])
        else:
            sheet.append([
                filename,
                "",
                status,
                "",
                file_result.get("message", ""),
            ])

    autofit_worksheet(sheet, max_width=90)
    return sheet


def build_standard_ocr_sheet(workbook, response_results):
    sheet = workbook.create_sheet(title=unique_sheet_title(workbook, "OCR Results"))
    headers = ["File", "Page", "Status", "Text", "Message"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for file_result in response_results:
        filename = file_result.get("filename", "")
        status = file_result.get("status", "")
        pages = file_result.get("pages", [])

        if isinstance(pages, list) and pages:
            for page in pages:
                sheet.append([
                    filename,
                    page.get("page_number", ""),
                    status,
                    page.get("text", ""),
                    "",
                ])
        else:
            sheet.append([
                filename,
                "",
                status,
                "",
                file_result.get("message", ""),
            ])

    autofit_worksheet(sheet, max_width=90)
    return sheet


def split_text_into_chunks(text, max_chars=3000):
    text = text or ""
    if not text.strip():
        return []
    
    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_length = 0
    
    for line in lines:
        if len(line) > max_chars:
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
            for i in range(0, len(line), max_chars):
                chunks.append(line[i:i+max_chars])
        elif current_length + len(line) + 1 > max_chars:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_length = len(line)
        else:
            current_chunk.append(line)
            current_length += len(line) + 1
            
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
        
    return [c.strip() for c in chunks if c.strip()]


def trim_text_for_llm(text, max_chars=LLM_INPUT_MAX_CHARS):
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip()


def extract_json_object(text):
    if not text:
        return None

    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)

    try:
        return json.loads(candidate)
    except Exception:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(candidate[start:end + 1])
            except Exception:
                return None
    return None


def call_ollama_structured_table(file_name, page_text):
    page_text = trim_text_for_llm(page_text, LLM_INPUT_MAX_CHARS)
    prompt = f"""
You convert raw OCR text extracted from a document into one or more clean, spreadsheet-friendly logical tables.

Input document filename: {file_name}

Structuring Rules:
1. **Analyze and Detect Logical Tables**:
   - Carefully analyze the document content. A single document may contain multiple logical tables.
   - For example, an invoice typically has:
     - A "Thông tin chung" (General Info) table containing metadata like Invoice No, Date, Buyer, Seller, Payment Method, Total Amount. This should be structured as a 2-column key-value table: ["Trường thông tin / Attribute", "Giá trị / Value"].
     - A "Chi tiết hàng hóa" (Line Items) table containing a grid of the goods or services, quantities, prices, etc. This should be structured as a multi-column table (e.g. headers: ["STT", "Tên hàng hóa", "Số lượng", "Đơn giá", "Thành tiền"]).
   - Extract each table separately. Do NOT force distinct tables or metadata and grids to combine into a single messy sheet.

2. **Clean and Standardize Data**:
   - For key-value pairs (e.g., "Số hóa đơn: HD-00123"), split them into headers and values. The attribute name should be in the first column, and the value in the second column (do not keep "Số hóa đơn: HD-00123" combined in a single cell).
   - Clean up OCR noise (like stray symbols "|", vertical lines, bullet points, leading/trailing colons ":", and extraneous spaces).
   - Use professional Vietnamese terminology for table names, headers, and values (e.g., "Mã hàng", "Số lượng", "Đơn giá", "Thành tiền", "Ngày lập", "Thông tin chung").

3. **Response Schema**:
   - Return ONLY a JSON object with this exact shape:
     {{
       "tables": [
         {{
           "name": "Tên bảng ngắn gọn bằng tiếng Việt (ví dụ: Thông tin chung, Danh sách sản phẩm, v.v.)",
           "headers": ["Header 1", "Header 2", ...],
           "rows": [
             {{
               "Header 1": "value 1",
               "Header 2": "value 2"
             }}
           ]
         }}
       ],
       "notes": "Nhận xét ngắn gọn về cấu trúc dữ liệu đã trích xuất"
     }}
   - Each sheet name must be under 25 characters to fit Excel's 31-character limit.
   - Use empty strings for missing values.

OCR text to structure:
{page_text}
""".strip()

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": CLASSIFIER_MODEL,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": 0,
                "num_predict": LLM_OUTPUT_MAX_TOKENS,
            },
            "messages": [
                {
                    "role": "system",
                    "content": "You are a careful data extraction engine that returns valid JSON only.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        },
        timeout=(10, 180),
    )
    response.raise_for_status()
    payload = response.json()
    message = payload.get("message", {})
    content = message.get("content", "")
    parsed = extract_json_object(content)
    if not isinstance(parsed, dict):
        raise ValueError("Ollama response did not contain valid JSON.")
    return parsed



def normalize_llm_rows(llm_result, filename, page_number):
    headers = llm_result.get("headers", [])
    rows = llm_result.get("rows", [])

    normalized_rows = []
    if not isinstance(headers, list):
        headers = []
    headers = [normalize_cell_value(header) for header in headers if normalize_cell_value(header)]

    for row in rows if isinstance(rows, list) else []:
        row_dict = {"File": filename, "Page": page_number, "Status": "llm"}
        if isinstance(row, dict):
            for header in headers:
                row_dict[header] = normalize_cell_value(row.get(header, ""))
            for key, value in row.items():
                key_name = normalize_cell_value(key)
                if key_name and key_name not in row_dict:
                    row_dict[key_name] = normalize_cell_value(value)
        elif isinstance(row, (list, tuple)):
            for index, header in enumerate(headers):
                row_dict[header] = normalize_cell_value(row[index]) if index < len(row) else ""
        else:
            row_dict["Value"] = normalize_cell_value(row)
        normalized_rows.append(row_dict)

    if not normalized_rows and headers:
        normalized_rows.append({"File": filename, "Page": page_number, **{header: "" for header in headers}})

    return normalized_rows


def style_worksheet_premium(sheet):
    if not sheet:
        return

    # Colors and styles
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid") # Navy Blue
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    
    zebra_fill = PatternFill(start_color="F2F5F8", end_color="F2F5F8", fill_type="solid") # Soft blue-gray
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    
    # 1. Format Headers (Row 1)
    sheet.row_dimensions[1].height = 28
    headers = []
    for col_idx in range(1, sheet.max_column + 1):
        cell = sheet.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        headers.append(str(cell.value or "").strip().lower())

    # Helper function to check if string looks like numeric
    def is_numeric(val_str):
        if not val_str:
            return False
        cleaned = val_str.strip().replace(",", "").replace(".", "").replace("$", "").replace("%", "").replace("đ", "").replace("VND", "").replace("vnđ", "")
        return cleaned.isdigit()

    # 2. Format Data Rows
    for row_idx in range(2, sheet.max_row + 1):
        sheet.row_dimensions[row_idx].height = 20
        is_even = (row_idx % 2 == 0)
        row_fill = zebra_fill if is_even else None
        
        for col_idx in range(1, sheet.max_column + 1):
            cell = sheet.cell(row=row_idx, column=col_idx)
            cell.font = Font(name="Segoe UI", size=10)
            cell.border = thin_border
            if row_fill:
                cell.fill = row_fill
                
            val_str = str(cell.value or "").strip()
            header = headers[col_idx - 1] if col_idx - 1 < len(headers) else ""
            
            # Smart alignment
            is_num_col = any(k in header for k in ["giá", "tiền", "số lượng", "qty", "amount", "total", "price", "thành tiền", "đơn giá", "chi phí", "thuế", "tax", "doanh thu"])
            is_num_val = is_numeric(val_str)
            
            is_center_col = any(k in header for k in ["page", "trang", "status", "trạng thái", "ngày", "date", "stt", "no."])
            
            if is_num_col or (is_num_val and len(val_str) < 15):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif is_center_col or (len(val_str) <= 10 and not val_str.count(" ")):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                # Text wrapping for long sentences
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # 3. Smart Auto-Fit Columns
    for col_idx in range(1, sheet.max_column + 1):
        column_cells = [sheet.cell(row=r, column=col_idx) for r in range(1, sheet.max_row + 1)]
        column_letter = column_cells[0].column_letter
        
        longest = 0
        has_long_text = False
        for cell in column_cells:
            cell_value = str(cell.value or "").strip()
            if cell_value:
                lines = cell_value.splitlines()
                cell_longest_line = max(len(line) for line in lines) if lines else 0
                longest = max(longest, cell_longest_line)
                if len(cell_value) > 30:
                    has_long_text = True
                    
        if has_long_text:
            width = 40
        else:
            width = min(max(longest + 3, 12), 30)
            
        sheet.column_dimensions[column_letter].width = width



def build_llm_structured_sheet(workbook, response_results):
    notes = []
    created_sheets = set()
    
    # Helper to clean and sanitize title, then find or create matching sheet
    def get_target_sheet(title, headers):
        title_str = normalize_cell_value(title).strip()
        if not title_str:
            title_str = "Dữ liệu phân tích"
            
        base_title = sanitize_sheet_title(title_str, fallback="Dữ liệu phân tích")
        
        # Check if we already created a sheet with similar name and matching headers
        for sheet_name in workbook.sheetnames:
            if sheet_name.lower().startswith(base_title.lower()[:20]):
                sheet = workbook[sheet_name]
                # Check headers matching
                existing_headers = [c.value for c in sheet[1]]
                # Exclude 'Tên file'
                if len(existing_headers) >= 1 and existing_headers[:1] == ["Tên file"]:
                    existing_headers = existing_headers[1:]
                if existing_headers == headers:
                    return sheet
                    
        # Otherwise create a new sheet
        sheet_name = unique_sheet_title(workbook, base_title, fallback="Dữ liệu phân tích")
        sheet = workbook.create_sheet(title=sheet_name)
        sheet.append(["Tên file"] + headers)
        created_sheets.add(sheet)
        return sheet

    # Fallback sheet for unstructured pages or failures
    fallback_sheet = None
    def get_fallback_sheet():
        nonlocal fallback_sheet
        if fallback_sheet is None:
            sheet_name = unique_sheet_title(workbook, "Chưa phân loại", fallback="Chưa phân loại")
            fallback_sheet = workbook.create_sheet(title=sheet_name)
            fallback_sheet.append(["Tên file", "Trạng thái", "Chi tiết / Văn bản"])
            created_sheets.add(fallback_sheet)
        return fallback_sheet

    for file_result in response_results:
        filename = file_result.get("filename", "")
        status = file_result.get("status", "")
        pages = file_result.get("pages", [])

        if status != "success" or not isinstance(pages, list) or not pages:
            f_sheet = get_fallback_sheet()
            f_sheet.append([filename, status or "error", file_result.get("message", "Lỗi xử lý file.")])
            continue

        # Combine text of all pages in the file
        combined_texts = []
        for p in pages:
            p_num = p.get("page_number", 1)
            p_txt = str(p.get("text", "")).strip()
            if p_txt:
                combined_texts.append(f"--- TRANG {p_num} ---\n{p_txt}")

        full_file_text = "\n\n".join(combined_texts).strip()
        if not full_file_text:
            continue

        try:
            llm_result = call_ollama_structured_table(filename, full_file_text)
            
            # The new structured prompt returns a dict with "tables": [...]
            tables = llm_result.get("tables", [])
            if not isinstance(tables, list):
                # Fallback to single table if LLM returned old schema
                if isinstance(llm_result.get("headers"), list):
                    tables = [llm_result]
                else:
                    tables = []
                    
            for table in tables:
                title = table.get("name") or table.get("title") or "Dữ liệu phân tích"
                headers = table.get("headers", [])
                rows = table.get("rows", [])
                
                if not isinstance(headers, list):
                    headers = []
                if not isinstance(rows, list):
                    rows = []
                    
                headers = [normalize_cell_value(h).strip() for h in headers if normalize_cell_value(h).strip()]
                
                if headers and rows:
                    sheet = get_target_sheet(title, headers)
                    for row in rows:
                        row_values = [filename]
                        if isinstance(row, dict):
                            for h in headers:
                                row_values.append(normalize_cell_value(row.get(h, "")))
                        elif isinstance(row, (list, tuple)):
                            for idx, h in enumerate(headers):
                                row_values.append(normalize_cell_value(row[idx]) if idx < len(row) else "")
                        else:
                            row_values.append(normalize_cell_value(row))
                            row_values.extend([""] * (len(headers) - 1))
                        sheet.append(row_values)
                else:
                    # Fallback for empty or unstructured table output
                    f_sheet = get_fallback_sheet()
                    f_sheet.append([filename, "unstructured", str(table)])
                    
            llm_note = normalize_cell_value(llm_result.get("notes", "")).strip()
            if llm_note:
                notes.append(f"{filename}: {llm_note}")
                
        except Exception as exc:
            notes.append(f"{filename}: Gặp lỗi khi gọi LLM ({exc}).")
            f_sheet = get_fallback_sheet()
            f_sheet.append([filename, "error", f"Lỗi gọi LLM: {exc}. Nội dung văn bản xem tại tệp TXT."])

    # If no sheets were created, create a default empty sheet
    if not created_sheets:
        empty_sheet = workbook.create_sheet(title="Kết quả trống")
        empty_sheet.append(["Tên file", "Thông báo"])
        empty_sheet.append(["", "Không trích xuất được dữ liệu có cấu trúc từ tài liệu."])
        created_sheets.add(empty_sheet)

    # Apply styling & auto-fit columns for all created sheets
    for sheet in created_sheets:
        style_worksheet_premium(sheet)

    if notes:
        notes_sheet = workbook.create_sheet(title=unique_sheet_title(workbook, "LLM Notes"))
        notes_sheet.append(["Thông tin phản hồi từ LLM"])
        notes_sheet[1][0].font = Font(name="Segoe UI", size=11, bold=True)
        for note in notes:
            notes_sheet.append([note])
        style_worksheet_premium(notes_sheet)

    return workbook.worksheets[0]


def build_excel_report(response_results, use_llm=False):
    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    if use_llm:
        build_llm_structured_sheet(workbook, response_results)
        build_raw_ocr_sheet(workbook, response_results)
    else:
        build_standard_ocr_sheet(workbook, response_results)

    # Style all worksheets in the workbook
    for sheet in workbook.worksheets:
        style_worksheet_premium(sheet)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def process_image_ocr(pil_img, import_type="clear", layout_preserve=False):
    detector = get_detector(import_type)
    img_np = np.array(pil_img)
    results = detector.predict(img_np)
    
    raw_boxes = []
    if results:
        items = results if isinstance(results, (list, tuple)) else [results]
        for item in items:
            if item is None:
                continue
            if hasattr(item, "get"):
                # PP-OCRv5 format
                boxes = []
                for key in ["dt_polys", "rec_polys", "rec_boxes"]:
                    val = item.get(key)
                    if val is not None:
                        if isinstance(val, np.ndarray):
                            if val.size > 0:
                                boxes = val
                                break
                        elif len(val) > 0:
                            boxes = val
                            break
                raw_boxes.extend(boxes)
            elif isinstance(item, (list, tuple)):
                # Legacy formats
                for sub_item in item:
                    if sub_item is None or len(sub_item) < 1:
                        continue
                    raw_boxes.append(sub_item[0])

    page_lines = []
    for idx, box in enumerate(raw_boxes):
        cropped = crop_box(pil_img, box, padding=3)
        if cropped is None:
            continue
        try:
            text, prob = recognizer.predict(cropped, return_prob=True)
            text = text.strip()
            if text:
                page_lines.append({
                    "text": text,
                    "box": box,
                    "confidence": float(prob)
                })
        except Exception:
            continue
            
    if layout_preserve:
        return format_layout_preserving(page_lines)
    else:
        sorted_lines = sort_lines(page_lines)
        return "\n".join([line["text"] for line in sorted_lines])

def process_docx_text(file_path):
    try:
        import docx
        doc = docx.Document(file_path)
        paragraphs_text = []
        total_chars = 0
        max_chars_allowed = MAX_DOCX_TEXT_CHARS
        
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text = paragraph.text.strip()
                total_chars += len(text)
                if total_chars > max_chars_allowed:
                    raise ValueError(f"Tài liệu Word vượt quá giới hạn ký tự cho phép (tối đa {max_chars_allowed} ký tự).")
                paragraphs_text.append(text)
        
        # Extract table texts
        for table in doc.tables:
            for row in table.rows:
                row_cells = []
                for cell in row.cells:
                    if cell not in row_cells:
                        row_cells.append(cell)
                row_text = " | ".join(cell.text.strip() for cell in row_cells if cell.text.strip())
                if row_text:
                    total_chars += len(row_text)
                    if total_chars > max_chars_allowed:
                        raise ValueError(f"Tài liệu Word vượt quá giới hạn ký tự cho phép (tối đa {max_chars_allowed} ký tự).")
                    paragraphs_text.append(row_text)
                    
        return "\n".join(paragraphs_text)
    except ValueError as ve:
        raise ve
    except Exception as e:
        raise ValueError(f"Không thể đọc file Word: {str(e)}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ready",
        "engine": "paddle_vietocr"
    })


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/ocr', methods=['POST'])
def run_ocr():
    if 'files' not in request.files:
        return jsonify({"error": "No file part in the request (must upload to 'files' field)"}), 400
        
    uploaded_files = request.files.getlist('files')
    if not uploaded_files or uploaded_files[0].filename == '':
        return jsonify({"error": "No selected files"}), 400

    import_type = normalize_import_type(request.form.get("import_type"))
    import_type_label = OCR_IMPORT_TYPES[import_type]["label"]
    layout_preserve = request.form.get("layout_preserve", "false").lower() == "true"
    cleanup_storage_older_than(STORAGE_RETENTION_DAYS)
        
    response_results = []
 
    for file in uploaded_files:
        raw_filename = file.filename or "untitled"
        
        # Check individual file size before processing/OCR
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset pointer
        if file_size > MAX_UPLOAD_FILE_SIZE_BYTES:
            response_results.append({
                "filename": raw_filename,
                "status": "error",
                "message": "Dung lượng file vượt quá giới hạn cho phép (tối đa 10MB mỗi file)."
            })
            continue
        
        # Check extension whitelist first
        _, ext = os.path.splitext(raw_filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            response_results.append({
                "filename": raw_filename,
                "status": "error",
                "message": "Định dạng tệp không được hỗ trợ."
            })
            continue
 
        # Check file content signature (magic numbers)
        if not check_file_signature(file, ext):
            response_results.append({
                "filename": raw_filename,
                "status": "error",
                "message": "Nội dung tệp không hợp lệ hoặc đã bị thay đổi phần mở rộng trái phép."
            })
            continue
 
        filename = secure_filename(raw_filename)
        if not filename:
            filename = f"file_{tempfile.mktemp().split('tmp')[-1]}"
        storage_paths = build_storage_paths(raw_filename)

        print(f"Processing uploaded file: {raw_filename} -> {filename}")
        
        # Save file to a temporary file
        fd, temp_path = tempfile.mkstemp()
        pdf_doc = None
        pages_text = []
        try:
            with os.fdopen(fd, 'wb') as tmp:
                file.save(tmp)

            preflight_input_file(temp_path, filename)
            with open(storage_paths["input_path"], "wb") as stored_input:
                with open(temp_path, "rb") as source_input:
                    stored_input.write(source_input.read())
            
            if filename.lower().endswith(".pdf"):
                pdf_doc = pdfium.PdfDocument(temp_path)
                num_pages = len(pdf_doc)
                if num_pages > 20:
                    raise ValueError(f"Tài liệu PDF vượt quá giới hạn số trang cho phép (tối đa 20 trang, file này có {num_pages} trang).")
                for i, page in enumerate(pdf_doc):
                    bitmap = page.render(scale=2.0)
                    pil_img = bitmap.to_pil()
                    text = process_image_ocr(pil_img, import_type=import_type, layout_preserve=layout_preserve)
                    pages_text.append({
                        "page_number": i + 1,
                        "text": text
                    })
            elif filename.lower().endswith(".docx"):
                text = process_docx_text(temp_path)
                pages_text.append({
                    "page_number": 1,
                    "text": text
                })
            else:
                pil_img = Image.open(temp_path).convert("RGB")
                text = process_image_ocr(pil_img, import_type=import_type, layout_preserve=layout_preserve)
                pages_text.append({
                    "page_number": 1,
                    "text": text
                })
            output_payload = build_ocr_output_payload(
                filename=filename,
                import_type=import_type,
                layout_preserve=layout_preserve,
                pages_text=pages_text,
                saved_at=storage_paths["saved_at"],
            )
            write_ocr_output_json(storage_paths["output_path"], output_payload)

            response_results.append({
                "filename": filename,
                "status": "success",
                "pages": pages_text
            })
            
        except Exception as e:
            try:
                error_payload = build_ocr_output_payload(
                    filename=filename,
                    import_type=import_type,
                    layout_preserve=layout_preserve,
                    pages_text=pages_text,
                    saved_at=storage_paths["saved_at"],
                    status="error",
                    message=str(e),
                )
                write_ocr_output_json(storage_paths["output_path"], error_payload)
            except Exception as storage_error:
                print(f"Warning: could not write OCR error output for {filename}: {storage_error}")
            response_results.append({
                "filename": filename,
                "status": "error",
                "message": str(e)
            })
        finally:
            if pdf_doc is not None:
                try:
                    close_fn = getattr(pdf_doc, "close", None)
                    if callable(close_fn):
                        close_fn()
                except Exception:
                    pass
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as cleanup_error:
                    print(f"Warning: could not remove temp file {temp_path}: {cleanup_error}")
                
    return jsonify({
        "status": "success",
        "import_type": import_type,
        "import_type_label": import_type_label,
        "layout_preserve": layout_preserve,
        "results": response_results
    })


@app.route('/export/xlsx', methods=['POST'])
def export_xlsx():
    payload = request.get_json(silent=True) or {}
    results = payload.get("results")
    use_llm = bool(payload.get("use_llm"))

    if not isinstance(results, list):
        return jsonify({"error": "Missing OCR results for Excel export."}), 400

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    workbook_bytes = build_excel_report(results, use_llm=use_llm)

    return send_file(
        workbook_bytes,
        as_attachment=True,
        download_name=f"ocr-result-{timestamp}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

if __name__ == '__main__':
    # Run on local port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
