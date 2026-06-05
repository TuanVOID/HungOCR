import os
import json
import re
import sys
import tempfile
from datetime import datetime
from io import BytesIO

import numpy as np
from PIL import Image
from flask import Flask, request, jsonify, render_template, send_file
import pypdfium2 as pdfium
import requests
from openpyxl import Workbook
from openpyxl.styles import Font

# Ensure UTF-8 printing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.0.6:11434").rstrip("/")
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "qwen3.5:9b-q4_K_M")

# Global model placeholders
detector = None
recognizer = None
local_weights = 'C:/Indti/project-gitclone/deepdoc_vietocr/vietocr/weight/vgg_seq2seq.pth'

def init_models():
    global detector, recognizer
    print("Initializing models globally...")
    from paddleocr import PaddleOCR
    from vietocr.tool.predictor import Predictor
    from vietocr.tool.config import Cfg

    # Initialize PaddleOCR detector (CPU by default)
    detector = PaddleOCR(
        lang="vi",
        device="cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True
    )

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
    return str(value)


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


def truncate_for_llm(text, max_chars=14000):
    text = text or ""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


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


def call_ollama_structured_table(file_name, page_number, page_text):
    prompt = f"""
You convert OCR text into spreadsheet-friendly structured data.

Input document:
- File: {file_name}
- Page: {page_number}

Rules:
- Infer the most useful columns from the OCR text.
- Prefer real table or form structure over raw text.
- If the page is a list or table, return one row per item.
- If it is a form, return one row with the form fields as columns.
- If it is mostly unstructured, still make the best effort using columns like Field/Value, Item/Detail, or similar.
- Do not include File or Page in the returned headers or rows.
- Return JSON only with this exact shape:
  {{"title":"short sheet title","headers":["Column 1","Column 2"],"rows":[{{"Column 1":"value","Column 2":"value"}}],"notes":"short optional note"}}
- Use empty strings for missing values.
- Keep values concise and clean.

OCR text:
{page_text}
""".strip()

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": CLASSIFIER_MODEL,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
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


def build_llm_structured_sheet(workbook, response_results):
    sheet = workbook.create_sheet(title=unique_sheet_title(workbook, "LLM Structured"))
    all_rows = []
    notes = []

    for file_result in response_results:
        filename = file_result.get("filename", "")
        status = file_result.get("status", "")
        pages = file_result.get("pages", [])

        if status != "success" or not isinstance(pages, list) or not pages:
            all_rows.append({
                "File": filename,
                "Page": "",
                "Status": status or "error",
                "Text": "",
                "Message": file_result.get("message", ""),
            })
            continue

        for page in pages:
            page_number = page.get("page_number", "")
            page_text = normalize_cell_value(page.get("text", "")).strip()
            if not page_text:
                continue

            clipped_text, was_truncated = truncate_for_llm(page_text)
            try:
                llm_result = call_ollama_structured_table(filename, page_number, clipped_text)
                page_rows = normalize_llm_rows(llm_result, filename, page_number)
                llm_note = normalize_cell_value(llm_result.get("notes", "")).strip()
                if llm_note:
                    notes.append(f"{filename} page {page_number}: {llm_note}")
                if was_truncated:
                    notes.append(f"{filename} page {page_number}: OCR text was truncated before LLM extraction.")
                if not page_rows:
                    page_rows.append({
                        "File": filename,
                        "Page": page_number,
                        "Text": page_text,
                    })
                all_rows.extend(page_rows)
            except Exception as exc:
                notes.append(f"{filename} page {page_number}: LLM fallback used ({exc}).")
                fallback_row = {
                    "File": filename,
                    "Page": page_number,
                    "Status": "fallback",
                    "Message": normalize_cell_value(exc),
                    "Text": page_text,
                }
                all_rows.append(fallback_row)

    if not all_rows:
        all_rows.append({"File": "", "Page": "", "Text": ""})

    headers = []
    for row in all_rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)

    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row in all_rows:
        sheet.append([normalize_cell_value(row.get(header, "")) for header in headers])

    autofit_worksheet(sheet, max_width=90)

    if notes:
        notes_sheet = workbook.create_sheet(title=unique_sheet_title(workbook, "LLM Notes"))
        notes_sheet.append(["Note"])
        notes_sheet[1][0].font = Font(bold=True)
        for note in notes:
            notes_sheet.append([note])
        autofit_worksheet(notes_sheet, max_width=120)

    return sheet


def build_excel_report(response_results, use_llm=False):
    workbook = Workbook()
    default_sheet = workbook.active
    workbook.remove(default_sheet)

    if use_llm:
        build_llm_structured_sheet(workbook, response_results)
        build_raw_ocr_sheet(workbook, response_results)
    else:
        build_standard_ocr_sheet(workbook, response_results)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer

def process_image_ocr(pil_img):
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
            
    sorted_lines = sort_lines(page_lines)
    return "\n".join([line["text"] for line in sorted_lines])

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
        
    response_results = []
    
    for file in uploaded_files:
        filename = file.filename
        print(f"Processing uploaded file: {filename}")
        
        # Save file to a temporary file
        fd, temp_path = tempfile.mkstemp()
        pdf_doc = None
        try:
            with os.fdopen(fd, 'wb') as tmp:
                file.save(tmp)
                
            pages_text = []
            
            if filename.lower().endswith(".pdf"):
                pdf_doc = pdfium.PdfDocument(temp_path)
                for i, page in enumerate(pdf_doc):
                    bitmap = page.render(scale=2.0)
                    pil_img = bitmap.to_pil()
                    text = process_image_ocr(pil_img)
                    pages_text.append({
                        "page_number": i + 1,
                        "text": text
                    })
            else:
                pil_img = Image.open(temp_path).convert("RGB")
                text = process_image_ocr(pil_img)
                pages_text.append({
                    "page_number": 1,
                    "text": text
                })
                
            response_results.append({
                "filename": filename,
                "status": "success",
                "pages": pages_text
            })
            
        except Exception as e:
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
