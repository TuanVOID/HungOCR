import os
import sys
import time
import requests
from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def generate_pdf_21pages(filename="limit_test_21pages.pdf"):
    print(f"Generating PDF with 21 pages: {filename}...")
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument.new()
    for _ in range(21):
        doc.new_page(200, 200)
    doc.save(filename)
    print("PDF created.")

def generate_docx_30k(filename="limit_test_30k.docx"):
    print(f"Generating Word document with 30,005 characters: {filename}...")
    import docx
    doc = docx.Document()
    # Write paragraph with >30000 characters
    long_text = "Tài liệu kiểm thử giới hạn ký tự. " * 1000 # 33 characters * 1000 = 33,000 characters
    doc.add_paragraph(long_text)
    doc.save(filename)
    print("Word document created.")

def generate_image_large_pixels(filename="limit_test_large_pixels.png"):
    print(f"Generating Image with 25 million pixels (5000x5000): {filename}...")
    img = Image.new("RGB", (5000, 5000), color="white")
    img.save(filename)
    print("Image created.")

def generate_image_long_edge(filename="limit_test_long_edge.png"):
    print(f"Generating Image with edge 12,001 px (12001x1): {filename}...")
    img = Image.new("RGB", (12001, 1), color="white")
    img.save(filename)
    print("Image created.")

def generate_heavy_file(filename="limit_test_heavy.docx"):
    print(f"Generating 11 MB dummy Word file: {filename}...")
    # Starts with PK\x03\x04 to pass signature checks, followed by 11MB of random/empty bytes
    with open(filename, "wb") as f:
        f.write(b"PK\x03\x04")
        f.write(b"\x00" * (11 * 1024 * 1024))
    print("Heavy file created.")

def run_limit_tests():
    base_url = "http://127.0.0.1:8092"
    ocr_url = f"{base_url}/ocr"
    
    test_cases = {
        "PDF with 21 pages": "limit_test_21pages.pdf",
        "Word with >30k characters": "limit_test_30k.docx",
        "Image with 25M pixels": "limit_test_large_pixels.png",
        "Image with edge 12001px": "limit_test_long_edge.png",
        "Heavy file (11MB)": "limit_test_heavy.docx"
    }
    
    all_passed = True
    print("\n--- Starting Backend Limit Restriction Tests ---")
    
    for desc, filepath in test_cases.items():
        print(f"\n[Test Case] Sending {desc} ({filepath})...")
        if not os.path.exists(filepath):
            print(f"Error: {filepath} was not generated.")
            all_passed = False
            continue
            
        try:
            with open(filepath, 'rb') as f:
                files = [('files', (os.path.basename(filepath), f, 'application/octet-stream'))]
                data = {
                    "import_type": "clear",
                    "layout_preserve": "true"
                }
                response = requests.post(ocr_url, files=files, data=data, timeout=30)
                
            print(f"HTTP Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                results_list = result.get("results", [])
                if results_list:
                    status = results_list[0].get("status")
                    message = results_list[0].get("message", "")
                    print(f"Server response status: {status}")
                    print(f"Server message: {message}")
                    if status == "error":
                        print(f"-> SUCCESS: Server correctly rejected the request with message.")
                    else:
                        print(f"-> FAILURE: Server accepted the file but it should have been rejected!")
                        all_passed = False
                else:
                    print("-> FAILURE: Empty results in response.")
                    all_passed = False
            elif response.status_code == 413:
                print("HTTP Status 413: Request Entity Too Large.")
                print("-> SUCCESS: Server correctly blocked the request via Flask MAX_CONTENT_LENGTH.")
            else:
                print(f"-> FAILURE: Unexpected HTTP status code: {response.status_code}, body: {response.text}")
                all_passed = False
        except Exception as e:
            print(f"Exception while running test for {desc}: {e}")
            all_passed = False
            
    return all_passed

if __name__ == "__main__":
    files = {
        "pdf": "limit_test_21pages.pdf",
        "docx": "limit_test_30k.docx",
        "img_pixels": "limit_test_large_pixels.png",
        "img_edge": "limit_test_long_edge.png",
        "heavy": "limit_test_heavy.docx"
    }
    
    try:
        generate_pdf_21pages(files["pdf"])
        generate_docx_30k(files["docx"])
        generate_image_large_pixels(files["img_pixels"])
        generate_image_long_edge(files["img_edge"])
        generate_heavy_file(files["heavy"])
        
        success = run_limit_tests()
        if success:
            print("\nAll limit tests completed successfully. Server correctly enforced safety constraints!")
        else:
            print("\nSome limit tests failed. Please review the errors.")
    finally:
        print("\nCleaning up temporary test files...")
        for name, path in files.items():
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"Removed: {path}")
                except Exception as e:
                    print(f"Failed to remove {path}: {e}")
