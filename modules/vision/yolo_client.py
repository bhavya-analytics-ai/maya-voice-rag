"""
sprint7/vision/yolo_client.py
Wraps the YOLOv8 3-class endpoint (Aquapro, Montecarlo, Smart).
Returns (class_name, confidence) or (None, 0.0) on failure/low conf.
"""
import os
import requests
from langsmith.run_helpers import traceable

YOLO_ENDPOINT = os.getenv("YOLO_ENDPOINT", "http://localhost:8001/predict")
CONFIDENCE_THRESHOLD = float(os.getenv("YOLO_CONF_THRESHOLD", "0.4"))


@traceable(name="yolo_detect", run_type="tool")
def yolo_detect(image_bytes: bytes, filename: str = "image.jpg") -> tuple:
    """
    POST image to YOLOv8 endpoint.
    Returns (class_name, confidence) for the top detection if conf >= threshold.
    class_name is one of: 'Aquapro', 'Montecarlo', 'Smart'
    Returns (None, 0.0) if no confident detection.
    """
    try:
        resp = requests.post(
            YOLO_ENDPOINT,
            files={"file": (filename, image_bytes, "image/jpeg")},
            data={"conf": CONFIDENCE_THRESHOLD, "task": "detection"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        detections = data.get("detections", [])
        if not detections:
            return None, 0.0

        # Pick highest confidence detection
        top = max(detections, key=lambda d: d.get("confidence", 0))
        label = top.get("class_name", "")
        conf = float(top.get("confidence", 0.0))

        if label and conf >= CONFIDENCE_THRESHOLD:
            return label, conf
        return None, conf

    except Exception:
        return None, 0.0
