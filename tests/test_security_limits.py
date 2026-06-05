import unittest
from io import BytesIO
import sys
import os

# Add root folder to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import split_text_into_chunks, check_file_signature, normalize_cell_value, process_docx_text

class TestSecurityLimits(unittest.TestCase):
    
    def test_split_text_into_chunks(self):
        # Test case: normal small text
        text = "Hello World\nLine 2"
        chunks = split_text_into_chunks(text, max_chars=50)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], "Hello World\nLine 2")
        
        # Test case: splitting long text
        text_long = "\n".join([f"This is line {i}" for i in range(20)])
        chunks_long = split_text_into_chunks(text_long, max_chars=100)
        self.assertTrue(len(chunks_long) > 1)
        # Ensure no chunk exceeds 100 characters
        for chunk in chunks_long:
            self.assertTrue(len(chunk) <= 100)
            
    def test_normalize_cell_value_formula_injection(self):
        # Safe string
        self.assertEqual(normalize_cell_value("Hello"), "Hello")
        # Formula strings
        self.assertEqual(normalize_cell_value("=SUM(A1:A5)"), "'=SUM(A1:A5)")
        self.assertEqual(normalize_cell_value("+1+2"), "'+1+2")
        self.assertEqual(normalize_cell_value("@dangerous"), "'@dangerous")
        # Negative numbers (should not be prepended with quote)
        self.assertEqual(normalize_cell_value("-123.45"), "-123.45")
        self.assertEqual(normalize_cell_value("-abc"), "'-abc")

    def test_check_file_signature(self):
        # Valid PNG signature
        png_stream = BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
        self.assertTrue(check_file_signature(png_stream, '.png'))
        
        # Invalid PNG signature (e.g. text file renamed)
        bad_png_stream = BytesIO(b'some standard text content here')
        self.assertFalse(check_file_signature(bad_png_stream, '.png'))
        
        # Valid PDF signature
        pdf_stream = BytesIO(b'%PDF-1.4\n%...')
        self.assertTrue(check_file_signature(pdf_stream, '.pdf'))
        
        # Valid DOCX signature
        docx_stream = BytesIO(b'PK\x03\x04\x14\x00\x08\x00\x08\x00')
        self.assertTrue(check_file_signature(docx_stream, '.docx'))

    def test_process_docx_text(self):
        import docx
        doc = docx.Document()
        doc.add_paragraph("Đây là đoạn văn bản test Word.")
        table = doc.add_table(rows=1, cols=2)
        row = table.rows[0]
        row.cells[0].text = "Cột 1"
        row.cells[1].text = "Cột 2"
        
        test_path = "test_temp_docx.docx"
        doc.save(test_path)
        
        try:
            extracted_text = process_docx_text(test_path)
            self.assertIn("Đây là đoạn văn bản test Word.", extracted_text)
            self.assertIn("Cột 1 | Cột 2", extracted_text)
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)

    def test_process_docx_text_limit(self):
        import docx
        doc = docx.Document()
        doc.add_paragraph("A" * 31000)
        
        test_path = "test_temp_docx_limit.docx"
        doc.save(test_path)
        
        try:
            with self.assertRaises(ValueError) as context:
                process_docx_text(test_path)
            self.assertIn("vượt quá giới hạn ký tự", str(context.exception))
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)

    @unittest.mock.patch('app.call_ollama_structured_table')
    def test_build_llm_structured_sheet(self, mock_call):
        from openpyxl import Workbook
        from app import build_llm_structured_sheet
        
        # Configure mock return values
        mock_call.side_effect = [
            {
                "title": "Hóa đơn mua hàng",
                "headers": ["Tên sản phẩm", "Số lượng", "Đơn giá"],
                "rows": [
                    {"Tên sản phẩm": "Bút bi", "Số lượng": "10", "Đơn giá": "5000"},
                    {"Tên sản phẩm": "Sổ tay", "Số lượng": "2", "Đơn giá": "25000"}
                ]
            },
            {
                "title": "Thông tin nhân sự",
                "headers": ["Trường thông tin", "Giá trị"],
                "rows": [
                    {"Trường thông tin": "Họ và tên", "Giá trị": "Nguyễn Văn A"},
                    {"Trường thông tin": "Chức vụ", "Giá trị": "Nhân viên"}
                ]
            }
        ]
        
        wb = Workbook()
        wb.remove(wb.active) # Remove default sheet
        
        mock_results = [
            {
                "filename": "document.pdf",
                "status": "success",
                "pages": [
                    {"page_number": 1, "text": "Some text content for page 1"},
                    {"page_number": 2, "text": "Some text content for page 2"}
                ]
            }
        ]
        
        build_llm_structured_sheet(wb, mock_results)
        
        # Verify sheets were created successfully
        self.assertIn("Hóa đơn mua hàng", wb.sheetnames)
        self.assertIn("Thông tin nhân sự", wb.sheetnames)
        
        # Verify content of "Hóa đơn mua hàng"
        sheet1 = wb["Hóa đơn mua hàng"]
        # Row 1 headers: File, Page, Tên sản phẩm, Số lượng, Đơn giá
        self.assertEqual([c.value for c in sheet1[1]], ["File", "Page", "Tên sản phẩm", "Số lượng", "Đơn giá"])
        # Row 2 data: document.pdf, 1, Bút bi, 10, 5000
        self.assertEqual([c.value for c in sheet1[2]], ["document.pdf", 1, "Bút bi", "10", "5000"])
        
        # Verify content of "Thông tin nhân sự"
        sheet2 = wb["Thông tin nhân sự"]
        self.assertEqual([c.value for c in sheet2[1]], ["File", "Page", "Trường thông tin", "Giá trị"])
        self.assertEqual([c.value for c in sheet2[2]], ["document.pdf", 2, "Họ và tên", "Nguyễn Văn A"])

if __name__ == '__main__':
    unittest.main()
