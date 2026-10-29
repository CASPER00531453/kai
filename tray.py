"""Notification-area icon. Lives behind the taskbar chevron, not as an app button."""

from __future__ import annotations

import pystray
from PIL import Image, ImageDraw

from i18n import t
from voice import MODELS, VOICES, voices as voice_list


def make_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((6, 18, 58, 46), radius=14, fill=(12, 12, 14, 255))
    draw.ellipse((14, 26, 26, 38), fill=(53, 184, 255, 255))
    draw.rounded_rectangle((32, 28, 36, 36), radius=2, fill=(255, 255, 255, 230))
    draw.rounded_rectangle((40, 24, 44, 40), radius=2, fill=(255, 255, 255, 230))
    draw.rounded_rectangle((48, 27, 52, 37), radius=2, fill=(255, 255, 255, 200))
    return img


def save_ico(path: str) -> None:
    img = make_image()
    img.save(path, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])


class Tray:
    def __init__(self, actions) -> None:
        self.actions = actions
        def size_item(percent: int) -> pystray.MenuItem:
            def choose(icon, item):
                actions["size"](percent)

            def is_on(item):
                return actions["size_is"](percent)

            return pystray.MenuItem(f"%{percent}", choose, checked=is_on, radio=True)

        def pick_item(label, value: str, kind: str) -> pystray.MenuItem:
            def choose(icon, item):
                actions[kind](value)

            def is_on(item):
                return actions[kind + "_is"](value)

            return pystray.MenuItem(label, choose, checked=is_on, radio=True)

        # Labels are callables so the menu follows the language without a restart.
        def said(key: str):
            return lambda item: t(key)

        voices = pystray.Menu(*[pick_item(lambda item, i=i: voice_list()[i][0], vid, "voice") for i, (_label, vid) in enumerate(VOICES)])
        models = pystray.Menu(*[pick_item(said(key), mid, "model") for key, mid in MODELS])

        menu = pystray.Menu(
            pystray.MenuItem("Kai", lambda icon, item: actions["mode"]("kai"), checked=lambda item: actions["mode_is"]("kai"), radio=True),
            pystray.MenuItem("Kai v2", lambda icon, item: actions["mode"]("v2"), checked=lambda item: actions["mode_is"]("v2"), radio=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(said("tray.dynamic"), lambda icon, item: actions["dynamic"](), checked=lambda item: actions["dynamic_on"]()),
            pystray.MenuItem(said("tray.screen"), lambda icon, item: actions["screen"](), checked=lambda item: actions["screen_on"]()),
            pystray.MenuItem(said("tray.dot"), lambda icon, item: actions["dot"](), checked=lambda item: actions["dot_on"]()),
            pystray.MenuItem(said("tray.chat"), lambda icon, item: actions["chat"](), checked=lambda item: actions["chat_on"]()),
            pystray.MenuItem(said("tray.mic"), lambda icon, item: actions["mic"](), checked=lambda item: actions["mic_on"]()),
            pystray.MenuItem(said("tray.size"), pystray.Menu(size_item(50), size_item(75), size_item(100), size_item(125), size_item(150))),
            pystray.MenuItem(said("tray.voice"), voices),
            pystray.MenuItem(said("tray.quality"), models),
            pystray.MenuItem(said("tray.startup"), lambda icon, item: actions["startup"](), checked=lambda item: actions["startup_on"]()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(said("tray.settings"), lambda icon, item: actions["settings"]()),
            pystray.MenuItem(said("tray.hooks"), lambda icon, item: actions["hooks"]()),
            pystray.MenuItem(said("tray.pause"), lambda icon, item: actions["pause"](), checked=lambda item: actions["pause_on"]()),
            pystray.MenuItem(said("tray.music"), lambda icon, item: actions["music"]()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: actions["version_label"](), None, enabled=False),
            pystray.MenuItem(lambda item: actions["update_label"](), lambda icon, item: actions["update"]()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(said("tray.quit"), lambda icon, item: actions["quit"]()),
        )
        self.icon = pystray.Icon("Kai", make_image(), "Kai", menu)

    def run(self) -> None:
        self.icon.run()

    def refresh(self) -> None:
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:
            pass

    def notify(self, message: str) -> None:
        try:
            self.icon.notify(message, "Kai")
        except Exception:
            pass
