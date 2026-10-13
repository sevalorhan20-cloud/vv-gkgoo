from __future__ import annotations

import importlib.util
import statistics
from pathlib import Path
from typing import Any


def opencv_available() -> bool:
    return importlib.util.find_spec("cv2") is not None


def detect_focus_x(source: Path, start: float, end: float, maximum_frames: int = 48) -> dict[str, Any]:
    if not opencv_available():
        return {"focus_x": 0.5, "engine": "center", "detections": 0}
    try:
        import cv2

        capture = cv2.VideoCapture(str(source))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 25)
        cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
        sample_count = max(1, min(maximum_frames, int(max(1, end - start) * 1.5)))
        centers: list[float] = []
        for index in range(sample_count):
            second = start + (end - start) * (index + 0.5) / sample_count
            capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            height, width = frame.shape[:2]
            if width <= 0:
                continue
            resize_width = min(640, width)
            ratio = resize_width / width
            small = cv2.resize(frame, (resize_width, max(1, int(height * ratio))))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(36, 36))
            if len(faces):
                face = max(faces, key=lambda box: int(box[2]) * int(box[3]))
                centers.append((float(face[0]) + float(face[2]) / 2) / resize_width)
        capture.release()
        if centers:
            focus = min(0.88, max(0.12, float(statistics.median(centers))))
            return {"focus_x": round(focus, 4), "engine": "opencv-face", "detections": len(centers)}
    except Exception:
        pass
    return {"focus_x": 0.5, "engine": "center", "detections": 0}
