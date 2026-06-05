import os

import pytest

from tools.benchmark_thuvienphapluat_legal_ocr import run_benchmark


pytestmark = pytest.mark.resource_intensive


def test_thuvienphapluat_legal_ocr_benchmark():
    if os.getenv("RUN_THUVIENPHAPLUAT_BENCHMARK") != "1":
        pytest.skip("Set RUN_THUVIENPHAPLUAT_BENCHMARK=1 to run the live legal OCR benchmark.")

    result = run_benchmark()

    assert result["sample_count"] > 0
    assert 0.0 <= result["weighted_accuracy"] <= 1.0
    assert 0.0 <= result["mean_accuracy"] <= 1.0
    assert os.path.exists(result["manifest_path"])
    assert os.path.exists(result["report_path"])
    assert os.path.exists(result["report_json_path"])
