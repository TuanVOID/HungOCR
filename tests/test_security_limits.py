import unittest
from io import BytesIO
import sys
import os

# Add root folder to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import split_text_into_chunks, check_file_signature, normalize_cell_value, process_docx_text, trim_text_for_llm, get_int_env, preflight_input_file, build_ocr_spellcheck_prompt, call_ollama_ocr_spellcheck, apply_ocr_spellcheck, apply_ocr_corrections, normalize_import_type, OCR_IMPORT_TYPES
from tools.benchmark_thuvienphapluat_legal_ocr import normalize_for_scoring

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

    def test_trim_text_for_llm(self):
        text = "A" * 4000
        trimmed = trim_text_for_llm(text, max_chars=3000)
        self.assertEqual(len(trimmed), 3000)
        self.assertEqual(trimmed, "A" * 3000)
        self.assertEqual(trim_text_for_llm("short text", max_chars=3000), "short text")

    def test_get_int_env(self):
        with unittest.mock.patch.dict(os.environ, {"TEST_INT_ENV": "6000"}, clear=False):
            self.assertEqual(get_int_env("TEST_INT_ENV", 123), 6000)
        with unittest.mock.patch.dict(os.environ, {"TEST_INT_ENV": "invalid"}, clear=False):
            self.assertEqual(get_int_env("TEST_INT_ENV", 123), 123)

    @unittest.mock.patch('app.pdfium.PdfDocument')
    def test_preflight_input_file_pdf_limit(self, mock_pdf_document):
        mock_pdf = unittest.mock.MagicMock()
        mock_pdf.__len__.return_value = 21
        mock_pdf_document.return_value = mock_pdf

        with self.assertRaises(ValueError) as context:
            preflight_input_file("sample.pdf", "sample.pdf")

        self.assertIn("PDF", str(context.exception))
        mock_pdf.close.assert_called()

    @unittest.mock.patch('app.Image.open')
    def test_preflight_input_file_image_limit(self, mock_image_open):
        mock_img = unittest.mock.MagicMock()
        mock_img.size = (200, 200)
        mock_image_open.return_value.__enter__.return_value = mock_img

        with unittest.mock.patch('app.MAX_IMAGE_PIXELS', 10000), unittest.mock.patch('app.MAX_IMAGE_EDGE', 1000):
            with self.assertRaises(ValueError) as context:
                preflight_input_file("sample.png", "sample.png")

        self.assertIn("áº¢nh", str(context.exception))
            
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
        doc.add_paragraph("ÄÃ¢y lÃ  Ä‘oáº¡n vÄƒn báº£n test Word.")
        table = doc.add_table(rows=1, cols=2)
        row = table.rows[0]
        row.cells[0].text = "Cá»™t 1"
        row.cells[1].text = "Cá»™t 2"
        
        test_path = "test_temp_docx.docx"
        doc.save(test_path)
        
        try:
            extracted_text = process_docx_text(test_path)
            self.assertIn("ÄÃ¢y lÃ  Ä‘oáº¡n vÄƒn báº£n test Word.", extracted_text)
            self.assertIn("Cá»™t 1 | Cá»™t 2", extracted_text)
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
            self.assertIn("vÆ°á»£t quÃ¡ giá»›i háº¡n kÃ½ tá»±", str(context.exception))
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
                "title": "HÃ³a Ä‘Æ¡n mua hÃ ng",
                "headers": ["TÃªn sáº£n pháº©m", "Sá»‘ lÆ°á»£ng", "ÄÆ¡n giÃ¡"],
                "rows": [
                    {"TÃªn sáº£n pháº©m": "BÃºt bi", "Sá»‘ lÆ°á»£ng": "10", "ÄÆ¡n giÃ¡": "5000"},
                    {"TÃªn sáº£n pháº©m": "Sá»• tay", "Sá»‘ lÆ°á»£ng": "2", "ÄÆ¡n giÃ¡": "25000"}
                ]
            },
            {
                "title": "ThÃ´ng tin nhÃ¢n sá»±",
                "headers": ["TrÆ°á»ng thÃ´ng tin", "GiÃ¡ trá»‹"],
                "rows": [
                    {"TrÆ°á»ng thÃ´ng tin": "Há» vÃ  tÃªn", "GiÃ¡ trá»‹": "Nguyá»…n VÄƒn A"},
                    {"TrÆ°á»ng thÃ´ng tin": "Chá»©c vá»¥", "GiÃ¡ trá»‹": "NhÃ¢n viÃªn"}
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
        self.assertIn("HÃ³a Ä‘Æ¡n mua hÃ ng", wb.sheetnames)
        self.assertIn("ThÃ´ng tin nhÃ¢n sá»±", wb.sheetnames)
        
        # Verify content of "HÃ³a Ä‘Æ¡n mua hÃ ng"
        sheet1 = wb["HÃ³a Ä‘Æ¡n mua hÃ ng"]
        # Row 1 headers: File, Page, TÃªn sáº£n pháº©m, Sá»‘ lÆ°á»£ng, ÄÆ¡n giÃ¡
        self.assertEqual([c.value for c in sheet1[1]], ["File", "Page", "TÃªn sáº£n pháº©m", "Sá»‘ lÆ°á»£ng", "ÄÆ¡n giÃ¡"])
        # Row 2 data: document.pdf, 1, BÃºt bi, 10, 5000
        self.assertEqual([c.value for c in sheet1[2]], ["document.pdf", 1, "BÃºt bi", "10", "5000"])
        
        # Verify content of "ThÃ´ng tin nhÃ¢n sá»±"
        sheet2 = wb["ThÃ´ng tin nhÃ¢n sá»±"]
        self.assertEqual([c.value for c in sheet2[1]], ["File", "Page", "TrÆ°á»ng thÃ´ng tin", "GiÃ¡ trá»‹"])
        self.assertEqual([c.value for c in sheet2[2]], ["document.pdf", 2, "Há» vÃ  tÃªn", "Nguyá»…n VÄƒn A"])

    @unittest.mock.patch('app.requests.post')
    def test_call_ollama_structured_table_payload_limits(self, mock_post):
        from app import call_ollama_structured_table

        mock_response = unittest.mock.Mock()
        mock_response.json.return_value = {
            "message": {
                "content": '{"title":"Báº£ng","headers":["Cá»™t 1"],"rows":[{"Cá»™t 1":"GiÃ¡ trá»‹"}],"notes":""}'
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        long_text = "X" * 7000
        result = call_ollama_structured_table("sample.pdf", long_text)

        self.assertEqual(result["title"], "Báº£ng")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertIn("think", payload)
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_predict"], 6000)

        user_message = payload["messages"][1]["content"]
        self.assertIn("X" * 6000, user_message)
        self.assertNotIn("X" * 6001, user_message)

    def test_spellcheck_prompt_structure(self):
        prompt = build_ocr_spellcheck_prompt("Xin chao")
        self.assertIn("<task>", prompt)
        self.assertIn("Return only exact typo corrections. Do not rewrite text.", prompt)
        self.assertIn("wrong must be copied exactly from the input text.", prompt)
        self.assertIn("Do not include any pair where wrong and correct are identical.", prompt)
        self.assertIn("<input_text><![CDATA[", prompt)
        self.assertIn("Xin chao", prompt)
        self.assertNotIn("clean_text", prompt)

    @unittest.mock.patch('app.requests.post')
    def test_call_ollama_ocr_spellcheck_payload(self, mock_post):
        mock_response = unittest.mock.Mock()
        mock_response.json.return_value = {
            "response": '{"corrections":[{"wrong":"Xin chao","correct":"Xin chÃ o"}]}'
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = call_ollama_ocr_spellcheck("Xin chao")
        self.assertEqual(result["corrections"], [{"wrong": "Xin chao", "correct": "Xin chÃ o"}])

        _, kwargs = mock_post.call_args
        self.assertTrue(kwargs["json"]["stream"] is False)
        self.assertFalse(kwargs["json"]["think"])
        self.assertEqual(kwargs["json"]["options"]["temperature"], 0.1)
        self.assertIn("Return only exact typo corrections. Do not rewrite text.", kwargs["json"]["prompt"])
        self.assertIn("Do not include any pair where wrong and correct are identical.", kwargs["json"]["prompt"])
        self.assertEqual(kwargs["json"]["format"]["required"], ["corrections"])
        self.assertNotIn("clean_text", kwargs["json"]["prompt"])

    @unittest.mock.patch('app.requests.post')
    def test_call_ollama_ocr_spellcheck_retries_once_on_invalid_json(self, mock_post):
        first_response = unittest.mock.Mock()
        first_response.json.return_value = {"response": "not valid json"}
        first_response.raise_for_status.return_value = None

        second_response = unittest.mock.Mock()
        second_response.json.return_value = {
            "response": '{"corrections":[{"wrong":"Xin chao","correct":"Xin chÃ o"}]}'
        }
        second_response.raise_for_status.return_value = None

        mock_post.side_effect = [first_response, second_response]

        result = call_ollama_ocr_spellcheck("Xin chao")

        self.assertEqual(result["corrections"], [{"wrong": "Xin chao", "correct": "Xin chÃ o"}])
        self.assertEqual(mock_post.call_count, 2)

    @unittest.mock.patch('app.call_ollama_ocr_spellcheck')
    def test_apply_ocr_spellcheck_chunks_large_text(self, mock_call):
        def _side_effect(chunk, chunk_index=None, chunk_total=None):
            self.assertLessEqual(len(chunk), 6000)
            return {
                "corrections": [],
            }

        mock_call.side_effect = _side_effect

        text = "A" * 20000
        result = apply_ocr_spellcheck(text, source_name="sample.pdf", page_number=1)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["text"], text)
        self.assertEqual(mock_call.call_count, 4)
        self.assertEqual([len(call.args[0]) for call in mock_call.call_args_list], [6000, 6000, 6000, 2000])

    @unittest.mock.patch('app.call_ollama_ocr_spellcheck')
    def test_apply_ocr_spellcheck_applies_corrections_only(self, mock_call):
        mock_call.return_value = {
            "corrections": [
                {"wrong": "Xin chao", "correct": "Xin chÃ o"},
                {"wrong": "hop dong", "correct": "há»£p Ä‘á»“ng"},
            ]
        }

        result = apply_ocr_spellcheck("Xin chao ve hop dong nay.", source_name="sample.pdf", page_number=1)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["text"], "Xin chÃ o ve há»£p Ä‘á»“ng nay.")
        self.assertEqual(
            result["corrections"],
            [
                {"wrong": "Xin chao", "correct": "Xin chÃ o", "replaced_count": 1},
                {"wrong": "hop dong", "correct": "há»£p Ä‘á»“ng", "replaced_count": 1},
            ],
        )

    def test_apply_ocr_corrections_filters_broad_and_suspicious(self):
        text = "Xin chao ve hop dong nay. 2026 va https://example.com"
        updated_text, applied = apply_ocr_corrections(
            text,
            [
                {"wrong": "Xin chao", "correct": "Xin chÃ o"},
                {"wrong": "hop dong", "correct": "há»£p Ä‘á»“ng"},
                {"wrong": "2026", "correct": "2025"},
                {"wrong": "https://example.com", "correct": "https://example.org"},
                {"wrong": "Äá»˜C Láº¬P Tá»° DO - Háº NH PHÃšC", "correct": "Äá»™c láº­p - Tá»± do - Háº¡nh phÃºc"},
            ],
        )

        self.assertEqual(updated_text, "Xin chÃ o ve há»£p Ä‘á»“ng nay. 2026 va https://example.com")
        self.assertEqual(
            applied,
            [
                {"wrong": "Xin chao", "correct": "Xin chÃ o", "replaced_count": 1},
                {"wrong": "hop dong", "correct": "há»£p Ä‘á»“ng", "replaced_count": 1},
            ],
        )

    def test_relaxed_scoring_normalizes_case_and_punctuation(self):
        left = "Äá»˜C Láº¬P Tá»° DO - Háº NH PHÃšC"
        right = "Äá»™c láº­p tá»± do- háº¡nh phÃºc"
        self.assertEqual(normalize_for_scoring(left), normalize_for_scoring(right))

    def test_import_type_aliases_fold_complex_into_clear(self):
        self.assertEqual(normalize_import_type("complex"), "clear")
        self.assertEqual(normalize_import_type("clear"), "clear")
        self.assertIn("complex_llm", OCR_IMPORT_TYPES)
        self.assertTrue(OCR_IMPORT_TYPES["complex_llm"]["llm_postprocess"])

if __name__ == '__main__':
    unittest.main()