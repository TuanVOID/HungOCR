import pypdfium2 as pdfium
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

pdf_path = "25-2025-nd-cp.signed_2pages.pdf"
print(f"Opening PDF: {pdf_path}")
doc = pdfium.PdfDocument(pdf_path)
print(f"Total pages: {len(doc)}")

for i, page in enumerate(doc):
    textpage = page.get_textpage()
    text = textpage.get_text_bounded()
    print(f"\n--- Page {i+1} (length: {len(text)}) ---")
    print(text[:300] + ("..." if len(text) > 300 else ""))
