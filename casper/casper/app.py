"""Casper'ın pencereleri: ana pencere + ikinci ekrandaki gözcü paneli."""

from __future__ import annotations

import json
import os
import threading
import time

from . import brain, db, llm, paths, secrets, winscreen
from .api import Api
from .watcher import Watcher

TITLE = "Casper Patrick Jane"


class CasperApp:
    def __init__(self) -> None:
        self.main = None
        self.overlay = None
        self.watcher = Watcher(self.emit)
        self.api = Api(self)

    # --- olaylar: Python -> arayüz -----------------------------------------------

    def emit(self, event: dict) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        for window in (self.main, self.overlay):
            if window is None:
                continue
            try:
                window.evaluate_js(f"window.casperEvent && window.casperEvent({payload})")
            except Exception:
                pass

    # --- ekranlar ve gözcü paneli ----------------------------------------------

    def screens(self) -> list[dict]:
        import webview

        out = []
        for i, s in enumerate(getattr(webview, "screens", []) or []):
            out.append({
                "index": i,
                "x": getattr(s, "x", 0),
                "y": getattr(s, "y", 0),
                "width": s.width,
                "height": s.height,
            })
        return out

    def _overlay_rect(self) -> tuple[int, int, int, int]:
        screens = self.screens()
        width = 420
        if not screens:
            return 40, 40, width, 700
        stored = db.get_setting("watch_overlay_screen")
        choice = -1 if stored is None else int(stored)
        if choice < 0 or choice >= len(screens):
            choice = 1 if len(screens) > 1 else 0  # otomatik: ikinci ekran varsa o
        s = screens[choice]
        height = max(400, s["height"] - 120)
        return s["x"] + s["width"] - width - 24, s["y"] + 48, width, height

    def place_overlay(self) -> None:
        if self.overlay is None:
            return
        x, y, w, h = self._overlay_rect()
        try:
            self.overlay.resize(w, h)
            self.overlay.move(x, y)
        except Exception:
            pass

    def show_overlay(self, show: bool) -> None:
        if self.overlay is None:
            return
        if show:
            self.place_overlay()
            self.overlay.show()
        else:
            self.overlay.hide()

    def start_watch(self) -> None:
        self.watcher.start()
        self.show_overlay(True)
        self.emit({"type": "watch", **self.watcher.status()})

    def stop_watch(self) -> None:
        self.watcher.stop()
        self.show_overlay(False)
        self.emit({"type": "watch", **self.watcher.status(), "running": False})

    # --- dosya pencereleri -------------------------------------------------------

    def open_files(self, file_types: tuple[str, ...]) -> list[str]:
        import webview

        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        result = self.main.create_file_dialog(kind, allow_multiple=True, file_types=file_types)
        return list(result or [])

    def open_folder(self) -> list[str]:
        import webview

        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        result = self.main.create_file_dialog(kind)
        return list(result or [])

    # --- gün sonu zamanlayıcısı ------------------------------------------------

    def _daily_loop(self) -> None:
        while True:
            time.sleep(60)
            try:
                if not db.get_setting("daily_auto") or not secrets.has_api_key():
                    continue
                hhmm = (db.get_setting("daily_time") or "23:30").strip()
                if time.strftime("%H:%M") < hhmm:
                    continue
                today = time.strftime("%Y-%m-%d")
                if db.row("SELECT 1 FROM summaries WHERE day = ?", (today,)):
                    continue
                self.emit({"type": "daily_start"})
                text = brain.daily_summary()
                self.emit({"type": "daily", "text": text, "day": today})
            except llm.LLMError as exc:
                self.emit({"type": "error", "text": f"Gün sonu raporu: {exc}"})
            except Exception as exc:
                self.emit({"type": "error", "text": f"Gün sonu raporu yazılamadı: {exc}"})

    # --- başlat ------------------------------------------------------------------

    def run(self, debug: bool = False) -> None:
        import webview

        winscreen.make_dpi_aware()
        db.connect()
        self.main = webview.create_window(
            TITLE,
            os.path.join(paths.UI_DIR, "index.html"),
            js_api=self.api,
            width=1180,
            height=800,
            min_size=(900, 600),
            background_color="#0d0f14",
        )
        x, y, w, h = self._overlay_rect()
        self.overlay = webview.create_window(
            "Casper · Gözcü",
            os.path.join(paths.UI_DIR, "overlay.html"),
            js_api=self.api,
            width=w,
            height=h,
            x=x,
            y=y,
            frameless=True,
            easy_drag=True,
            on_top=True,
            hidden=True,
            background_color="#0d0f14",
        )

        def on_closed():
            self.watcher.stop()
            try:
                self.overlay.destroy()
            except Exception:
                pass

        self.main.events.closed += on_closed
        threading.Thread(target=self._daily_loop, daemon=True).start()
        storage = os.path.join(paths.data_dir(), "webview")
        webview.start(debug=debug, private_mode=False, storage_path=storage)
