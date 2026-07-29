import os
import sys
from unittest.mock import patch

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app_backend


@pytest.fixture(autouse=True)
def reset_lifecycle_state():
    app_backend.detectors.clear()
    app_backend.recognizer = None
    app_backend.LIFECYCLE_STATE.update({
        "model_loaded": False,
        "batch_id": None,
        "last_batch_id": None,
        "mode_effective": None,
        "device_effective": None,
        "vram_before_mb": None,
        "vram_loaded_mb": None,
        "vram_after_unload_mb": None,
        "vram_released_mb": None,
        "vram_release_verified": False,
        "load_count": 0,
        "unload_count": 0,
        "active_ocr_requests": 0,
        "last_error": None,
    })
    yield
    app_backend.detectors.clear()
    app_backend.recognizer = None


def fake_init_models():
    app_backend.detectors["clear"] = object()
    app_backend.recognizer = object()


def fake_unload_models():
    app_backend.detectors.clear()
    app_backend.recognizer = None


def test_health_exposes_unloaded_exclusive_lifecycle():
    config = app_backend.OCRDeviceConfig(
        "gpu", "cuda:0", "paddle", "", "CPUExecutionProvider", 0, False
    )
    with patch.object(app_backend, "detect_ocr_devices", return_value=config):
        response = app_backend.app.test_client().get("/health")

    assert response.status_code == 200
    lifecycle = response.get_json()["lifecycle"]
    assert lifecycle["ownership"] in {"owned", "exclusive_lease"}
    assert lifecycle["model_loaded"] is False
    assert lifecycle["load_count"] == 0


def test_lifecycle_load_is_idempotent_and_rejects_competing_batch():
    client = app_backend.app.test_client()
    config = app_backend.OCRDeviceConfig(
        "gpu", "cuda:0", "paddle", "", "CPUExecutionProvider", 0, False
    )
    vram_values = iter((1000.0, 1500.0))
    with (
        patch.object(app_backend, "detect_ocr_devices", return_value=config),
        patch.object(app_backend, "init_models", side_effect=fake_init_models),
        patch.object(
            app_backend,
            "query_gpu_used_memory_mb",
            side_effect=lambda: next(vram_values),
        ),
    ):
        first = client.post(
            "/lifecycle/load",
            json={"batch_id": "batch-1", "mode": "clear", "device": "gpu"},
        )
        repeated = client.post(
            "/lifecycle/load",
            json={"batch_id": "batch-1", "mode": "clear", "device": "gpu"},
        )
        competing = client.post(
            "/lifecycle/load",
            json={"batch_id": "batch-2", "mode": "clear", "device": "gpu"},
        )

    assert first.status_code == 200
    assert first.get_json()["loaded_now"] is True
    assert repeated.status_code == 200
    assert repeated.get_json()["loaded_now"] is False
    assert repeated.get_json()["lifecycle"]["load_count"] == 1
    assert competing.status_code == 409


def test_lifecycle_unload_verifies_vram_and_is_idempotent():
    client = app_backend.app.test_client()
    app_backend.detectors["clear"] = object()
    app_backend.recognizer = object()
    app_backend.LIFECYCLE_STATE.update({
        "model_loaded": True,
        "batch_id": "batch-1",
        "last_batch_id": "batch-1",
        "mode_effective": "clear",
        "device_effective": "gpu",
        "vram_before_mb": 1000.0,
        "vram_loaded_mb": 1500.0,
        "load_count": 1,
    })

    with (
        patch.object(app_backend, "unload_models", side_effect=fake_unload_models),
        patch.object(app_backend, "query_post_unload_vram_mb", return_value=1010.0),
    ):
        first = client.post(
            "/lifecycle/unload",
            json={"batch_id": "batch-1", "verify_vram_release": True},
        )
        repeated = client.post(
            "/lifecycle/unload",
            json={"batch_id": "batch-1", "verify_vram_release": True},
        )

    assert first.status_code == 200
    assert first.get_json()["unload_succeeded"] is True
    assert first.get_json()["lifecycle"]["model_loaded"] is False
    assert first.get_json()["lifecycle"]["vram_release_verified"] is True
    assert first.get_json()["lifecycle"]["vram_released_mb"] == 490.0
    assert repeated.status_code == 200
    assert repeated.get_json()["already_unloaded"] is True


def test_lifecycle_load_rejects_cpu_effective_devices():
    config = app_backend.OCRDeviceConfig(
        "cpu", "cpu", "paddle", "", "CPUExecutionProvider", 0, False
    )
    with patch.object(app_backend, "detect_ocr_devices", return_value=config):
        response = app_backend.app.test_client().post(
            "/lifecycle/load",
            json={"batch_id": "batch-1", "mode": "clear", "device": "gpu"},
        )

    assert response.status_code == 503
    assert response.get_json()["lifecycle"]["model_loaded"] is False


def test_lifecycle_rejects_unsupported_mode_and_device():
    client = app_backend.app.test_client()
    assert client.post(
        "/lifecycle/load",
        json={"batch_id": "batch-1", "mode": "complex_llm", "device": "gpu"},
    ).status_code == 400
    assert client.post(
        "/lifecycle/load",
        json={"batch_id": "batch-1", "mode": "clear", "device": "cpu"},
    ).status_code == 400
