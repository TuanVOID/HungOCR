import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import targeted functions
from app_backend import detect_ocr_devices, app, _cached_ocr_devices

@pytest.fixture(autouse=True)
def reset_cached_devices():
    """Reset the global cached device config before each test."""
    global _cached_ocr_devices
    import app_backend
    app_backend._cached_ocr_devices = None
    yield
    app_backend._cached_ocr_devices = None

def test_detect_ocr_devices_cpu_forced():
    """Test that setting OCR_DEVICE=cpu forces CPU allocation."""
    env_mock = {
        "OCR_DEVICE": "cpu",
        "OCR_GPU_REQUIRED": "false",
        "OCR_GPU_INDEX": "0",
        "OCR_DETECTOR_BACKEND": "paddle",
    }
    with patch.dict(os.environ, env_mock):
        config = detect_ocr_devices()
        assert config.paddle_device == "cpu"
        assert config.torch_device == "cpu"
        assert config.onnx_provider == "CPUExecutionProvider"

def test_detect_ocr_devices_gpu_strict_fail_when_no_cuda():
    """Test that OCR_GPU_REQUIRED=true fails startup when no GPU is detected."""
    env_mock = {
        "OCR_DEVICE": "gpu",
        "OCR_GPU_REQUIRED": "true",
        "OCR_GPU_INDEX": "0",
        "OCR_DETECTOR_BACKEND": "paddle",
    }
    with patch.dict(os.environ, env_mock):
        # Mock torch.cuda.is_available as False
        with patch('torch.cuda.is_available', return_value=False):
            with pytest.raises(RuntimeError) as exc_info:
                detect_ocr_devices()
            assert "Strict CUDA Validation failed" in str(exc_info.value) or "PyTorch CUDA is not available" in str(exc_info.value)

def test_detect_ocr_devices_gpu_fallback_when_not_strict():
    """Test that OCR_DEVICE=gpu falls back to CPU when GPU not found and OCR_GPU_REQUIRED=false."""
    env_mock = {
        "OCR_DEVICE": "gpu",
        "OCR_GPU_REQUIRED": "false",
        "OCR_GPU_INDEX": "0",
        "OCR_DETECTOR_BACKEND": "paddle",
    }
    with patch.dict(os.environ, env_mock):
        with patch('torch.cuda.is_available', return_value=False), \
             patch('paddle.is_compiled_with_cuda', return_value=False):
            config = detect_ocr_devices()
            assert config.paddle_device == "cpu"
            assert config.torch_device == "cpu"

def test_detect_ocr_devices_onnxruntime_validation():
    """Test that OCR_DETECTOR_BACKEND=onnxruntime requires OCR_DETECTOR_ONNX_MODEL path."""
    env_mock = {
        "OCR_DEVICE": "cpu",
        "OCR_DETECTOR_BACKEND": "onnxruntime",
        "OCR_DETECTOR_ONNX_MODEL": ""
    }
    with patch.dict(os.environ, env_mock):
        with pytest.raises(ValueError) as exc_info:
            detect_ocr_devices()
        assert "OCR_DETECTOR_ONNX_MODEL must be configured" in str(exc_info.value)

def test_detect_ocr_devices_onnxruntime_invalid_model_path():
    """Test that invalid ONNX model path raises FileNotFoundError."""
    env_mock = {
        "OCR_DEVICE": "cpu",
        "OCR_DETECTOR_BACKEND": "onnxruntime",
        "OCR_DETECTOR_ONNX_MODEL": "non_existent_model.onnx"
    }
    with patch.dict(os.environ, env_mock):
        with pytest.raises(FileNotFoundError):
            detect_ocr_devices()

def test_health_endpoint_payload():
    """Test the detailed health endpoint response structure."""
    env_mock = {
        "OCR_DEVICE": "cpu",
        "OCR_GPU_REQUIRED": "false",
        "OCR_DETECTOR_BACKEND": "paddle",
    }
    with patch.dict(os.environ, env_mock):
        client = app.test_client()
        response = client.get('/health')
        assert response.status_code == 200
        
        json_data = response.get_json()
        assert json_data["status"] == "ready"
        assert json_data["engine"] == "extraction_ocr_engine"
        assert json_data["requested_device"] == "cpu"
        assert json_data["gpu_required"] is False
        
        # Verify detector structure
        assert "detector" in json_data
        assert json_data["detector"]["framework"] == "paddle"
        assert json_data["detector"]["device"] == "cpu"
        assert "verified" in json_data["detector"]
        
        # Verify recognizer structure
        assert "recognizer" in json_data
        assert json_data["recognizer"]["framework"] == "vietocr/pytorch"
        assert json_data["recognizer"]["device"] == "cpu"
        assert "verified" in json_data["recognizer"]
