import os

import pytest

from tools.benchmark_vietnamese_ocr_overall import run_overall_benchmark


pytestmark = pytest.mark.resource_intensive


def test_vietnamese_ocr_overall_benchmark():
    if os.getenv("RUN_VIETNAMESE_OCR_OVERALL_BENCHMARK") != "1":
        pytest.skip("Set RUN_VIETNAMESE_OCR_OVERALL_BENCHMARK=1 to run the live overall OCR benchmark.")

    result = run_overall_benchmark()

    assert result["sample_count"] == 40
    assert 0.0 <= result["weighted_accuracy"] <= 1.0
    assert 0.0 <= result["mean_accuracy"] <= 1.0
    assert os.path.exists(result["manifest_path"])
    assert os.path.exists(result["report_path"])
    assert os.path.exists(result["report_json_path"])
