import os
import sys
import numpy as np
import pytest
from PIL import Image

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ppocr.modeling.onnx_detector_adapter import ONNXDetectorAdapter
from app_backend import app, detect_ocr_devices, local_weights

# Helper to check GPU availability
def is_gpu_available():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False

# Skip all tests in this module if GPU is not available
pytestmark = pytest.mark.gpu_integration

@pytest.fixture(autouse=True)
def require_gpu():
    if not is_gpu_available():
        pytest.skip("No GPU/CUDA available on this environment. Skipping GPU integration tests.")

def test_torch_cuda_smoke():
    """Verify basic PyTorch CUDA operations work correctly."""
    import torch
    assert torch.cuda.is_available(), "CUDA should be available"
    
    device = torch.device("cuda:0")
    x = torch.randn(3, 3, device=device)
    y = torch.randn(3, 3, device=device)
    z = torch.matmul(x, y)
    torch.cuda.synchronize(device)
    
    assert z.device.type == "cuda"
    assert z.shape == (3, 3)
    print(f"Torch CUDA smoke test passed on: {torch.cuda.get_device_name(0)}")

def test_onnx_detector_cuda_smoke():
    """Verify ONNX detector initializes on CUDAExecutionProvider without CPU fallback."""
    import app_backend
    detector = app_backend.detectors.get("clear")
    assert detector is not None, "Detector was not initialized globally"
    
    # Verify CUDAExecutionProvider is the active provider
    active_providers = detector.session.get_providers()
    assert 'CUDAExecutionProvider' in active_providers, f"Active providers: {active_providers}. CUDAExecutionProvider missing!"
    
    # Run a smoke inference
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    res = detector.predict(dummy_img)
    assert isinstance(res, list)
    assert "dt_polys" in res[0]
    print("ONNX detector CUDA smoke test passed successfully!")

def test_vietocr_gpu_smoke():
    """Verify VietOCR predictor loads weights and performs inference on GPU."""
    import app_backend
    predictor = app_backend.recognizer
    assert predictor is not None, "Recognizer was not initialized globally"
    
    # Smoke inference
    dummy_crop = Image.fromarray(np.zeros((32, 120, 3), dtype=np.uint8))
    pred_text = predictor.predict(dummy_crop)
    assert isinstance(pred_text, str)
    print("VietOCR GPU smoke test passed successfully!")

def test_health_endpoint_gpu_status():
    """Test health endpoint returns GPU info when GPU is configured."""
    # This is a unit-style integration check. We mock config settings as GPU
    env_mock = {
        "OCR_DEVICE": "gpu",
        "OCR_GPU_REQUIRED": "true",
        "OCR_GPU_INDEX": "0",
        "OCR_DETECTOR_BACKEND": "onnxruntime",
        "OCR_DETECTOR_ONNX_MODEL": "models/onnx/PP-OCRv5_server_det/model.onnx",
        "OCR_ORT_DISABLE_CPU_FALLBACK": "true"
    }
    from unittest.mock import patch, MagicMock
    import app_backend
    app_backend._cached_ocr_devices = None
    
    with patch.dict(os.environ, env_mock), \
         patch('onnxruntime.InferenceSession') as mock_session:
        
        # Mock active providers for health endpoint
        mock_instance = MagicMock()
        mock_instance.get_providers.return_value = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        mock_session.return_value = mock_instance
        
        client = app.test_client()
        response = client.get('/health')
        assert response.status_code == 200
        json_data = response.get_json()
        
        assert json_data["requested_device"] == "gpu"
        assert json_data["gpu_required"] is True
        assert json_data["detector"]["device"] == "gpu"
        assert json_data["detector"]["provider"] == "CUDAExecutionProvider"
        assert json_data["detector"]["cpu_fallback"] is False
        assert "gpu_detail" in json_data
        assert json_data["gpu_detail"]["index"] == 0
