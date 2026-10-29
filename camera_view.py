"""Local camera window. Boxes stay on this PC, only names leave it."""

from __future__ import annotations

import threading

_stop = threading.Event()
_thread: threading.Thread | None = None
labels: list[str] = []


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, name="kai-camera", daemon=True)
    _thread.start()


def stop() -> None:
    global labels
    _stop.set()
    labels = []


def _run() -> None:
    global labels
    try:
        import cv2
    except Exception:
        labels = ["kamera yok"]
        return
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        labels = ["kamera yok"]
        return
    # OpenCV 5 dropped the old Haar CascadeClassifier; YuNet (ONNX) is the face
    # detector now. The model sits next to the app, same as live_view uses.
    import os
    import sys

    model = "face_detection_yunet_2023mar.onnx"
    root = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(__file__))
    model_path = next(
        (p for p in (os.path.join(root, "models", model), os.path.join(root, model)) if os.path.isfile(p)),
        "",
    )
    face = cv2.FaceDetectorYN.create(model_path, "", (640, 360), 0.6, 0.3, 5000) if model_path else None
    cv2.namedWindow("Kai kamera", cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty("Kai kamera", cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass
    while not _stop.is_set():
        ok, frame = cap.read()
        if not ok:
            break
        seen: list[str] = []
        if face is not None:
            height, width = frame.shape[:2]
            face.setInputSize((width, height))
            _count, found = face.detect(frame)
            for row in (found if found is not None else [])[:6]:
                x, y, w, h = [int(v) for v in row[:4]]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 190, 60), 2)
                cv2.putText(frame, "yuz", (x + w - 50, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 190, 60), 2)
                seen.append("yuz")
        labels = seen
        cv2.imshow("Kai kamera", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    cap.release()
    cv2.destroyWindow("Kai kamera")
    labels = []
