"""Pick a part of the screen with the mouse. The picture goes to Kai as a dropped file."""

from __future__ import annotations

import ctypes
import os
import threading

_busy = threading.Lock()

# Alt+Shift+S, from anywhere.
MOD_ALT, MOD_SHIFT, MOD_NOREPEAT = 0x0001, 0x0004, 0x4000
WM_HOTKEY = 0x0312
HOTKEY_ID = 0x4B41
# Alt+Shift+T: pick a part of the screen and have its text translated.
TRANSLATE_ID = 0x4B42


def _target() -> str:
    from settings import v2_file

    return v2_file("ekran-secimi.png")


def select() -> str | None:
    """Dim the screen, let the user drag a box, save what is inside. None when cancelled.

    Blocks until the box is drawn or Esc is pressed. One at a time: a second call
    while the first is open returns None at once.
    """
    if not _busy.acquire(blocking=False):
        return None
    try:
        return _select()
    finally:
        _busy.release()


def _select() -> str | None:
    import tkinter as tk

    from PIL import ImageEnhance, ImageGrab, ImageTk

    user32 = ctypes.windll.user32
    # The whole desktop, every monitor.
    left, top = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    shot = ImageGrab.grab(all_screens=True)

    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry(f"{width}x{height}+{left}+{top}")
    root.attributes("-topmost", True)
    root.configure(bg="black", cursor="crosshair")
    canvas = tk.Canvas(root, highlightthickness=0, bg="black")
    canvas.pack(fill="both", expand=True)
    root.update()
    # Tk and the screenshot may count pixels differently on a scaled display;
    # everything below goes through this ratio. A canvas that is not laid out
    # yet reports 1: then the size asked for stands.
    shown_w, shown_h = canvas.winfo_width(), canvas.winfo_height()
    if shown_w <= 1 or shown_h <= 1:
        shown_w, shown_h = width, height
    dim = ImageEnhance.Brightness(shot).enhance(0.45)
    if dim.size != (shown_w, shown_h):
        dim = dim.resize((shown_w, shown_h))
    backdrop = ImageTk.PhotoImage(dim, master=root)
    canvas.create_image(0, 0, image=backdrop, anchor="nw")
    box = canvas.create_rectangle(0, 0, 0, 0, outline="#35B8FF", width=2)
    label = canvas.create_text(0, 0, text="", fill="#f4f4f5", anchor="sw", font=("Segoe UI", 10))
    hint = "Sürükleyerek seç · Esc ile vazgeç" if _turkish() else "Drag to select · Esc to cancel"
    canvas.create_text(shown_w // 2, 28, text=hint, fill="#f4f4f5", font=("Segoe UI Semibold", 12))

    state: dict = {"start": None, "end": None, "live": None, "done": False}

    def press(event) -> None:
        state["start"] = (event.x, event.y)

    def drag(event) -> None:
        if not state["start"]:
            return
        x0, y0 = state["start"]
        canvas.coords(box, x0, y0, event.x, event.y)
        # The picked part shows at full brightness, so it is clear what Kai will see.
        a, b = min(x0, event.x), min(y0, event.y)
        c, d = max(x0, event.x), max(y0, event.y)
        if c - a > 2 and d - b > 2:
            part = shot.crop(_scaled((a, b, c, d), shot.size, (shown_w, shown_h)))
            if part.size != (c - a, d - b):
                part = part.resize((c - a, d - b))
            state["live"] = ImageTk.PhotoImage(part, master=root)
            canvas.delete("bright")
            canvas.create_image(a, b, image=state["live"], anchor="nw", tags="bright")
            canvas.tag_raise(box)
        canvas.coords(label, a, max(14, b - 4))
        canvas.itemconfigure(label, text=f"{abs(event.x - x0)} × {abs(event.y - y0)}")
        canvas.tag_raise(label)

    def release(event) -> None:
        if state["start"]:
            state["end"] = (event.x, event.y)
            state["done"] = True
        root.destroy()

    def cancel(_event=None) -> None:
        root.destroy()

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
    canvas.bind("<ButtonPress-3>", cancel)
    root.bind("<Escape>", cancel)
    root.focus_force()
    root.mainloop()

    if not state["done"]:
        return None
    (x0, y0), (x1, y1) = state["start"], state["end"]
    area = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    if area[2] - area[0] < 8 or area[3] - area[1] < 8:
        return None
    path = _target()
    shot.crop(_scaled(area, shot.size, (shown_w, shown_h))).save(path)
    return path if os.path.isfile(path) else None


def _scaled(area, image_size, shown_size) -> tuple[int, int, int, int]:
    """A box in the overlay's coordinates, as the screenshot's pixels."""
    sx, sy = image_size[0] / shown_size[0], image_size[1] / shown_size[1]
    return (int(area[0] * sx), int(area[1] * sy), int(area[2] * sx), int(area[3] * sy))


def _turkish() -> bool:
    try:
        import i18n

        return i18n.current() == "tr"
    except Exception:
        return True


def watch_hotkey(on_pressed, key: str = "S", hotkey_id: int = HOTKEY_ID) -> None:
    """Call on_pressed() on Alt+Shift+<key>, from a thread of its own. Returns at once."""

    def run() -> None:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, hotkey_id, MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, ord(key)):
            return  # another program holds the shortcut; the button still works
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY and message.wParam == hotkey_id:
                try:
                    on_pressed()
                except Exception:
                    pass

    threading.Thread(target=run, daemon=True).start()
