import os
import sys
import argparse
import time
import numpy as np
from PIL import Image
import pypdfium2 as pdfium

# Reconfigure stdout for UTF-8 on Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Import PaddleOCR and VietOCR
try:
    from paddleocr import PaddleOCR
    from vietocr.tool.predictor import Predictor
    from vietocr.tool.config import Cfg
    IMPORTS_OK = True
except ImportError as e:
    print(f"Error importing dependencies: {e}")
    IMPORTS_OK = False

def save_and_print(text, file_obj=None):
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            print(text.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8'))
        except Exception:
            pass
    if file_obj:
        file_obj.write(text + "\n")

def crop_box(image, box, padding=3):
    try:
        pts = np.array(box, dtype=np.float32)
        min_x = np.min(pts[:, 0])
        max_x = np.max(pts[:, 0])
        min_y = np.min(pts[:, 1])
        max_y = np.max(pts[:, 1])

        # Apply padding and clamp to image boundaries
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


def run_composite_ocr(file_path, output_txt_path, use_gpu=False, preserve_layout=False):
    if not IMPORTS_OK:
        print("Required libraries are not fully installed.")
        return

    # Check weights
    local_weights = 'C:/Indti/project-gitclone/deepdoc_vietocr/vietocr/weight/vgg_seq2seq.pth'
    if not os.path.exists(local_weights):
        print(f"Warning: Local weights not found at {local_weights}.")
        print("VietOCR will attempt to download weights from the internet.")
        
    out_dir = os.path.dirname(output_txt_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    out_file = open(output_txt_path, "w", encoding="utf-8")
    
    save_and_print("=" * 60, out_file)
    save_and_print(f"Running COMPOSITE (PaddleOCR + VietOCR) on: {file_path}", out_file)
    save_and_print("=" * 60, out_file)

    # 1. Initialize PaddleOCR
    save_and_print("Initializing PaddleOCR Detector...", out_file)
    device = "gpu" if use_gpu else "cpu"
    detector = PaddleOCR(
        lang="vi",
        device=device,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True
    )

    # 2. Initialize VietOCR
    save_and_print("Initializing VietOCR Recognizer (vgg_seq2seq)...", out_file)
    config = Cfg.load_config_from_name('vgg_seq2seq')
    config['device'] = 'cpu'
    config['predictor']['beamsearch'] = False
    if os.path.exists(local_weights):
        config['weights'] = local_weights
        save_and_print(f"Using local weights: {local_weights}", out_file)
    recognizer = Predictor(config)

    # 3. Load pages
    pages = []
    if file_path.lower().endswith(".pdf"):
        doc = pdfium.PdfDocument(file_path)
        save_and_print(f"Loaded PDF containing {len(doc)} pages.", out_file)
        for i, page in enumerate(doc):
            # Render page to PIL image
            bitmap = page.render(scale=2.0) # Render at 2x scale for better OCR accuracy
            pil_img = bitmap.to_pil()
            pages.append((i + 1, pil_img))
    else:
        pil_img = Image.open(file_path).convert("RGB")
        pages.append((1, pil_img))

    # 4. Perform OCR
    for page_num, img in pages:
        save_and_print(f"\n--- Processing Page {page_num} ---", out_file)
        img_np = np.array(img)
        
        # Detect boxes
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

        save_and_print(f"Detected {len(raw_boxes)} text blocks. Running recognition...", out_file)
        
        # Recognize crops
        page_lines = []
        for idx, box in enumerate(raw_boxes):
            cropped = crop_box(img, box, padding=3)
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
            except Exception as e:
                continue
                
        # Sort lines
        if preserve_layout:
            layout_text = format_layout_preserving(page_lines)
            save_and_print(layout_text, out_file)
        else:
            sorted_lines = sort_lines(page_lines)
            for line in sorted_lines:
                save_and_print(line["text"], out_file)
            
    out_file.close()
    print("\n" + "=" * 60)
    print(f"OCR results saved to: {output_txt_path}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PaddleOCR Detection + VietOCR Recognition.")
    parser.add_argument("input_path", help="Path to PDF file or image.")
    parser.add_argument("--output", default="ocr_results_vietocr.txt", help="Path to output text file.")
    parser.add_argument("--gpu", action="store_true", help="Use GPU for PaddleOCR detector.")
    parser.add_argument("--preserve-layout", action="store_true", help="Preserve spatial layout in plain text output.")
    args = parser.parse_args()
    
    run_composite_ocr(args.input_path, args.output, use_gpu=args.gpu, preserve_layout=args.preserve_layout)
