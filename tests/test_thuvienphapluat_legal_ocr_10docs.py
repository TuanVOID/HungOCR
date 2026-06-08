import json
import os
from pathlib import Path

import pytest

from tests.testing_utils import TEST_DATA_DIR
from tools.benchmark_thuvienphapluat_legal_ocr import run_benchmark


pytestmark = pytest.mark.resource_intensive

DOCUMENTS_FILE = TEST_DATA_DIR / "thuvienphapluat_legal_10docs.json"


def test_thuvienphapluat_legal_ocr_10docs_benchmark():
    if os.getenv("RUN_THUVIENPHAPLUAT_10DOCS_BENCHMARK") != "1":
        pytest.skip("Set RUN_THUVIENPHAPLUAT_10DOCS_BENCHMARK=1 to run the live 10-document legal OCR benchmark.")

    document_urls = json.loads(DOCUMENTS_FILE.read_text(encoding="utf-8"))
    assert len(document_urls) == 10

    result = run_benchmark(document_urls=document_urls, max_pages_per_document=1)

    unique_document_urls = {sample["document_url"] for sample in result["samples"]}
    assert result["sample_count"] == 10
    assert unique_document_urls == set(document_urls)
    assert all(sample["page_index"] == 1 for sample in result["samples"])
    assert 0.0 <= result["weighted_accuracy"] <= 1.0
    assert 0.0 <= result["mean_accuracy"] <= 1.0
    assert Path(result["output_dir"]).parent.name == "thuvienphapluat_legal_ocr_10docs_runs"
    assert os.path.exists(result["manifest_path"])
    assert os.path.exists(result["report_path"])
    assert os.path.exists(result["report_json_path"])
