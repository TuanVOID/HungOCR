import pypdfium2 as pdfium
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def check_pdf(path):
    print(f"\nChecking: {path}")
    try:
        doc = pdfium.PdfDocument(path)
        print(f"Pages: {len(doc)}")
        for i, page in enumerate(doc):
            text = page.get_textpage().get_text_bounded().strip()
            print(f"Page {i+1} text length: {len(text)}")
            if text:
                print("Preview:")
                print(text[:200])
    except Exception as e:
        print(f"Error: {e}")

check_pdf("langchain-paddleocr/tests/data/sample_pdf.pdf")
check_pdf("Storage/input/2026-06-09/11-19-36_cca3ef_27-bnv.pdf")
