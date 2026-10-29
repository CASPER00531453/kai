"""Topmost screen and camera windows. Boxes and names are drawn on the picture."""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageTk

import boxes
from i18n import t

_user32 = ctypes.windll.user32
_views: dict[str, tk.Toplevel] = {}
_root: tk.Tk | None = None
_root_ready = threading.Event()
_root_thread: threading.Thread | None = None
mark_screen = False
mark_camera = False


def open_view(master, mode: str) -> None:
    if mode not in {"watch", "camera"}:
        return
    if master is None:
        _ensure_root()
        if _root is not None:
            _root.after(0, lambda: _open(_root, mode))
        return
    _open(master, mode)


def close_views() -> None:
    target = _root
    if target is not None:
        try:
            target.after(0, _close_all)
            return
        except tk.TclError:
            pass
    _close_all()


def labels() -> list[str]:
    found: list[str] = []
    for mode, win in list(_views.items()):
        names = getattr(win, "seen", None) or []
        for name in names:
            if name not in found:
                found.append(name)
        if mode == "camera" and not names and getattr(win, "dead", False):
            found.append("kamera yok")
    return found[:12]


def _ensure_root() -> None:
    global _root_thread
    if _root_thread and _root_thread.is_alive():
        _root_ready.wait(3)
        return

    def run() -> None:
        global _root
        _root = tk.Tk()
        _root.withdraw()
        _root_ready.set()
        _root.mainloop()

    _root_ready.clear()
    _root_thread = threading.Thread(target=run, name="kai-live", daemon=True)
    _root_thread.start()
    _root_ready.wait(3)


def _close_all() -> None:
    for win in list(_views.values()):
        try:
            win.destroy()
        except tk.TclError:
            pass
    _views.clear()


def _open(master, mode: str) -> None:
    current = _views.get(mode)
    if current is not None:
        try:
            if current.winfo_exists():
                current.lift()
                current.focus_force()
                return
        except tk.TclError:
            pass
    win = tk.Toplevel(master)
    win.title("Kai ekran" if mode == "watch" else "Kai kamera")
    win.configure(bg="#05070b")
    win.geometry("1180x700+60+40")
    win.attributes("-topmost", True)
    win.seen = []
    win.dead = False
    label = tk.Label(win, bg="#05070b", bd=0)
    label.pack(fill="both", expand=True)
    win._photo = None
    win._cap = None
    win._face = None
    win._body = None
    _views[mode] = win
    win.protocol("WM_DELETE_WINDOW", lambda window=win, kind=mode: _drop(kind, window))
    win._closed = False
    win._latest = None
    win._shown = None
    win.lift()
    win.focus_force()
    threading.Thread(target=_worker, args=(win, mode), name=f"kai-{mode}", daemon=True).start()
    _tick(win, label, mode)


def _drop(mode: str, win: tk.Toplevel) -> None:
    win._closed = True
    _views.pop(mode, None)
    try:
        win.destroy()
    except tk.TclError:
        pass


def _model_path() -> str:
    name = "face_detection_yunet_2023mar.onnx"
    roots = [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.abspath(__file__)), os.path.dirname(sys.executable)]
    for root in roots:
        if not root:
            continue
        for path in (os.path.join(root, "models", name), os.path.join(root, name)):
            if os.path.isfile(path):
                return path
    return ""


def _open_camera(win: tk.Toplevel) -> None:
    import cv2

    cap = None
    for index in (0, 1, 2):
        trial = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not trial.isOpened():
            trial.release()
            continue
        ok, frame = trial.read()
        if not ok or frame is None:
            trial.release()
            continue
        trial.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        trial.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        trial.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap = trial
        break
    if cap is None:
        win.dead = True
        return
    win._cap = cap
    win._cv = cv2
    win._face = None
    win._face_size = None


def _worker(win: tk.Toplevel, mode: str) -> None:
    try:
        if mode == "camera":
            try:
                _open_camera(win)
            except Exception:
                win.dead = True
                win._cap = None
        while not getattr(win, "_closed", False):
            try:
                image = _screen() if mode == "watch" else _camera(win)
                win.seen = list(getattr(image, "seen", []))
                win._latest = image
            except Exception:
                pass
            time.sleep(0.45 if mode == "watch" else 0.12)
    finally:
        cap = getattr(win, "_cap", None)
        win._cap = None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


def _tick(win: tk.Toplevel, label: tk.Label, mode: str) -> None:
    try:
        if not win.winfo_exists():
            return
    except tk.TclError:
        return
    image = getattr(win, "_latest", None)
    if image is not None and image is not getattr(win, "_shown", None):
        try:
            photo = ImageTk.PhotoImage(image)
            win._photo = photo
            win._shown = image
            label.configure(image=photo)
        except tk.TclError:
            return
    try:
        win.after(300, lambda: _tick(win, label, mode))
    except tk.TclError:
        pass


def _font(size: int):
    path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeuib.ttf")
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _tag(draw: ImageDraw.ImageDraw, text: str, right: int, top: int, color: tuple[int, int, int]) -> None:
    face = _font(16)
    tw = int(draw.textlength(text, font=face)) + 14
    th = 24
    x = max(4, right - tw - 8)
    y = max(4, top + 6)
    draw.rounded_rectangle((x, y, x + tw, y + th), radius=6, fill=(8, 16, 28, 220))
    draw.text((x + 7, y + 3), text, font=face, fill=color + (255,))


def _screen() -> Image.Image:
    ox = _user32.GetSystemMetrics(76)
    oy = _user32.GetSystemMetrics(77)
    shot = ImageGrab.grab(all_screens=True)
    scale = min(720 / max(1, shot.width), 405 / max(1, shot.height), 1)
    if scale != 1:
        shot.thumbnail((max(1, int(shot.width * scale)), max(1, int(shot.height * scale))), Image.Resampling.BILINEAR)
    shot = shot.convert("RGBA")
    draw = ImageDraw.Draw(shot)
    seen: list[str] = []
    if mark_screen:
        for name, (left, top, right, bottom) in boxes.scan():
            folded = name.lower()
            if folded.startswith("kai ekran") or folded.startswith("kai kamera"):
                continue
            x1 = int((left - ox) * scale)
            y1 = int((top - oy) * scale)
            x2 = int((right - ox) * scale)
            y2 = int((bottom - oy) * scale)
            if x2 - x1 < 12 or y2 - y1 < 12:
                continue
            draw.rectangle((x1, y1, x2, y2), outline=(90, 210, 255, 255), width=3)
            _tag(draw, name, x2, y1, (230, 248, 255))
            if name not in seen:
                seen.append(name)
    shot.seen = seen
    return shot


def _face_detector(win: tk.Toplevel, width: int, height: int):
    if getattr(win, "_face", None) is not None and getattr(win, "_face_size", None) == (width, height):
        win._face.setInputSize((width, height))
        return win._face
    path = _model_path()
    if not path:
        return None
    det = win._cv.FaceDetectorYN.create(path, "", (width, height), 0.6, 0.3, 5000)
    det.setInputSize((width, height))
    win._face = det
    win._face_size = (width, height)
    return det


def _camera(win: tk.Toplevel) -> Image.Image:
    cap = getattr(win, "_cap", None)
    if cap is None:
        image = Image.new("RGB", (640, 360), (8, 10, 16))
        draw = ImageDraw.Draw(image)
        draw.text((40, 160), t("camera_failed"), font=_font(28), fill=(255, 120, 120))
        image.seen = []
        return image
    cv2 = win._cv
    ok, frame = cap.read()
    if not ok or frame is None:
        image = Image.new("RGB", (640, 360), (8, 10, 16))
        image.seen = []
        return image
    height, width = frame.shape[:2]
    if width > 640:
        small = 640 / width
        frame = cv2.resize(frame, (640, max(1, int(height * small))))
        height, width = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb).convert("RGBA")
    draw = ImageDraw.Draw(image)
    seen: list[str] = []

    def mark(rects, text, color) -> None:
        for rect in list(rects)[:6]:
            x, y, w, h = [int(v) for v in list(rect)[:4]]
            draw.rectangle((x, y, x + w, y + h), outline=color + (255,), width=3)
            _tag(draw, text, x + w, y, color)
            if text not in seen:
                seen.append(text)

    if mark_camera:
        det = _face_detector(win, width, height)
        if det is not None:
            try:
                _count, faces = det.detect(frame)
            except Exception:
                faces = None
            if faces is not None:
                mark(faces, "yuz", (255, 196, 70))
    image.seen = seen
    return image
