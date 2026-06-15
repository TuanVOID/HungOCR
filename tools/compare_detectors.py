import os
from dotenv import load_dotenv
load_dotenv()

# Configure thread limits for computational libraries
for env_var in ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    val = os.getenv(env_var)
    if val is not None and val.strip() != "":
        os.environ[env_var] = val.strip()

import time
import numpy as np
import cv2
from PIL import Image

# Import ONNX detector adapter
from ppocr.modeling.onnx_detector_adapter import ONNXDetectorAdapter

def main():
    image_path = "test_ocr_input.png"
    if not os.path.exists(image_path):
        print(f"Error: {image_path} does not exist.")
        return

    print(f"Loading test image: {image_path}")
    # Load image using OpenCV (BGR format) or PIL
    img_cv = cv2.imread(image_path)
    if img_cv is None:
        print("Failed to load image via OpenCV.")
        return
    # Convert BGR to RGB for consistent preprocessing
    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    
    print("\n--- Initializing PaddlePaddle CPU Detector ---")
    try:
        from paddleocr import TextDetection
        paddle_detector = TextDetection(device="cpu", enable_mkldnn=True)
        print("PaddlePaddle CPU Detector initialized.")
    except Exception as e:
        print(f"Failed to initialize PaddlePaddle CPU Detector: {e}")
        paddle_detector = None

    print("\n--- Initializing ONNXRuntime CPU Detector ---")
    onnx_model_path = "models/onnx/PP-OCRv5_server_det/model.onnx"
    if not os.path.exists(onnx_model_path):
        print(f"ONNX model file not found at: {onnx_model_path}")
        return
    try:
        onnx_detector = ONNXDetectorAdapter(
            model_file=onnx_model_path,
            provider='CPUExecutionProvider'
        )
        print("ONNXRuntime CPU Detector initialized.")
    except Exception as e:
        print(f"Failed to initialize ONNX Detector: {e}")
        onnx_detector = None

    # Run comparison
    results_compare = {}

    if paddle_detector:
        print("\n--- Running PaddlePaddle CPU Detector Inference ---")
        # Warmup
        _ = paddle_detector.predict(img_rgb)
        
        # Benchmarking
        start_time = time.time()
        for i in range(5):
            res_paddle = paddle_detector.predict(img_rgb)
        end_time = time.time()
        avg_time = (end_time - start_time) / 5.0
        
        # Get boxes
        dt_boxes = res_paddle[0]["dt_polys"]
        print(f"PaddlePaddle detected {len(dt_boxes)} boxes.")
        print(f"Average Inference Time: {avg_time:.4f} seconds")
        results_compare["paddle"] = {
            "boxes": dt_boxes,
            "avg_time": avg_time
        }

    if onnx_detector:
        print("\n--- Running ONNXRuntime CPU Detector Inference ---")
        # Warmup
        _ = onnx_detector.predict(img_rgb)
        
        # Benchmarking
        start_time = time.time()
        for i in range(5):
            res_onnx = onnx_detector.predict(img_rgb)
        end_time = time.time()
        avg_time = (end_time - start_time) / 5.0
        
        # Get boxes
        dt_boxes = res_onnx[0]["dt_polys"]
        print(f"ONNXRuntime detected {len(dt_boxes)} boxes.")
        print(f"Average Inference Time: {avg_time:.4f} seconds")
        results_compare["onnx"] = {
            "boxes": dt_boxes,
            "avg_time": avg_time
        }

    # Analyze differences
    if "paddle" in results_compare and "onnx" in results_compare:
        paddle_boxes = results_compare["paddle"]["boxes"]
        onnx_boxes = results_compare["onnx"]["boxes"]
        
        print("\n--- Comparison Analysis ---")
        print(f"Paddle Box Count: {len(paddle_boxes)}")
        print(f"ONNX Box Count:   {len(onnx_boxes)}")
        
        diff_count = abs(len(paddle_boxes) - len(onnx_boxes))
        if diff_count == 0:
            print("Status: SUCCESS - Same number of boxes detected!")
        else:
            print(f"Status: WARNING - Difference in box count: {diff_count}")
            
        # Compare first 3 boxes coordinates if available
        limit = min(3, len(paddle_boxes), len(onnx_boxes))
        for idx in range(limit):
            print(f"\nComparing Box #{idx+1}:")
            print(f"Paddle: \n{paddle_boxes[idx]}")
            print(f"ONNX:   \n{onnx_boxes[idx]}")
            # Calculate distance
            dist = np.mean(np.abs(paddle_boxes[idx] - onnx_boxes[idx]))
            print(f"Mean Absolute Difference: {dist:.4f} pixels")
            
        time_ratio = results_compare["paddle"]["avg_time"] / results_compare["onnx"]["avg_time"]
        print(f"\nSpeedup: ONNX is {time_ratio:.2f}x faster/slower than Paddle CPU")

if __name__ == "__main__":
    main()
