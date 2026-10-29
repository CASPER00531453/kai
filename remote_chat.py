"""Small always-on-top box so the other person can type back."""

from __future__ import annotations

import queue
import threading
import tkinter as tk

from i18n import t


class ChatBox:
    def __init__(self, on_send) -> None:
        self.on_send = on_send
        self._queue: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        threading.Thread(target=self._ui, name="kai-remote-chat", daemon=True).start()
        self._ready.wait(4)

    def push(self, who: str, text: str) -> None:
        self._queue.put((who, text))

    def _ui(self) -> None:
        root = tk.Tk()
        root.title("Kai sohbet")
        root.configure(bg="#12141a")
        root.attributes("-topmost", True)
        root.geometry(f"380x300+{root.winfo_screenwidth() - 420}+48")
        log = tk.Text(
            root,
            bg="#1c1f27",
            fg="#f4f4f6",
            insertbackground="#f4f4f6",
            relief="flat",
            font=("Segoe UI", 11),
            wrap="word",
            state="disabled",
        )
        log.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        entry = tk.Entry(root, bg="#1c1f27", fg="#f4f4f6", insertbackground="#f4f4f6", relief="flat", font=("Segoe UI", 12))
        entry.pack(fill="x", padx=10, ipady=6)

        def send(_event=None) -> None:
            text = entry.get().strip()
            if not text:
                return
            entry.delete(0, "end")
            self._write(log, "Sen", text)
            try:
                self.on_send(text)
            except Exception:
                pass

        entry.bind("<Return>", send)
        tk.Button(root, text=t("send"), command=send, bg="#3aa0e8", fg="#081018", relief="flat", font=("Segoe UI", 10, "bold")).pack(
            fill="x", padx=10, pady=8
        )

        def pump() -> None:
            try:
                while True:
                    who, text = self._queue.get_nowait()
                    self._write(log, who, text)
            except queue.Empty:
                pass
            root.after(150, pump)

        root.after(150, pump)
        self._ready.set()
        root.mainloop()

    def _write(self, log: tk.Text, who: str, text: str) -> None:
        log.configure(state="normal")
        log.insert("end", f"{who}: {text}\n")
        log.configure(state="disabled")
        log.see("end")
