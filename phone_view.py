"""The phone looks at the computer's screen or camera, live (phone_link.py, capability "view").

Frames are JPEG, sent in parts of at most 45 000 base64 characters so no line
of the link nears 64 KiB. One frame in flight: the next is made only once the
phone says it has the last one (frameAck), so nothing piles up on a slow link
and what the phone shows is never old. The size and quality follow how fast
the acks come back.

Off by default (Kai window › Phone). While anyone looks, Kai on the island
holds a camera to its eye or a magnifying glass (island.ts), so the person at
the computer always sees that they are being looked at.
"""

from __future__ import annotations

import base64
import io
import json
import threading
import time

PART = 45_000
ACK_TIMEOUT = 3.0
# (longest side in pixels, JPEG quality): the viewer moves along it with the link's speed.
STEPS = [(640, 45), (800, 50), (960, 55), (1280, 60), (1600, 65)]


class Viewer:
    """One phone looking at one source; runs on its own thread until stopped."""

    def __init__(self, send, source: str, on_change, relayed: bool = False) -> None:
        self.send = send
        # Through the Cloudflare relay: at most 30 messages a second are let through, so
        # fewer, bigger parts and fewer frames; on the LAN and Tailscale it goes as fast as it can.
        self.part = 60_000 if relayed else PART
        self.min_gap = 0.25 if relayed else 0.08
        self.source = source
        self.on_change = on_change
        self._acked = threading.Event()
        self._acked.set()
        self._stop = threading.Event()
        self._frame = 0
        self._step = 1
        self.error = ""

    def ack(self, frame_id) -> None:
        if frame_id == self._frame:
            self._acked.set()

    def stop(self) -> None:
        self._stop.set()
        self._acked.set()

    def start(self) -> None:
        threading.Thread(target=self._run, name=f"kai-view-{self.source}", daemon=True).start()

    # -------------------------------------------------------------------------

    def _run(self) -> None:
        camera = None
        try:
            if self.source == "camera":
                import cv2

                camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                if not camera.isOpened():
                    self._tell(False, "no_camera")
                    return
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self._tell(True, "")
            self.on_change(self.source)
            while not self._stop.is_set():
                # Wait for the phone to have the last frame: never two in flight.
                if not self._acked.wait(ACK_TIMEOUT):
                    self._step = max(0, self._step - 1)
                    self._acked.set()
                    continue
                if self._stop.is_set():
                    break
                started = time.monotonic()
                data = self._grab(camera)
                if data is None:
                    time.sleep(0.2)
                    continue
                self._acked.clear()
                self._frame += 1
                if not self._send_frame(data):
                    break
                self._adapt(started)
        except Exception as exc:
            self.error = type(exc).__name__
        finally:
            if camera is not None:
                try:
                    camera.release()
                except Exception:
                    pass
            self._tell(False, "stopped")
            self.on_change("")

    def _grab(self, camera) -> bytes | None:
        from PIL import Image

        if camera is not None:
            import cv2

            ok, frame = camera.read()
            if not ok:
                return None
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        else:
            from PIL import ImageGrab

            image = ImageGrab.grab(all_screens=False)
        side, quality = STEPS[self._step]
        image.thumbnail((side, side), Image.BILINEAR)
        out = io.BytesIO()
        image.convert("RGB").save(out, "JPEG", quality=quality, optimize=False)
        return out.getvalue()

    def _send_frame(self, data: bytes) -> bool:
        text = base64.b64encode(data).decode("ascii")
        parts = [text[i:i + self.part] for i in range(0, len(text), self.part)] or [""]
        for index, chunk in enumerate(parts):
            line = json.dumps({"type": "frame", "id": self._frame, "part": index, "parts": len(parts), "data": chunk})
            if not self.send(line):
                return False
        return True

    def _adapt(self, started: float) -> None:
        """Quick acks: a bigger, sharper picture. Slow ones: a smaller one, so the motion stays live."""
        waited = self._acked.wait(ACK_TIMEOUT)
        took = time.monotonic() - started
        if not waited:
            return
        if took < 0.12 and self._step < len(STEPS) - 1:
            self._step += 1
        elif took > 0.35 and self._step > 0:
            self._step -= 1
        # At most about twelve frames a second: enough to be live, light on the computer.
        rest = self.min_gap - took
        if rest > 0:
            time.sleep(rest)

    def _tell(self, active: bool, reason: str) -> None:
        self.send(json.dumps({"type": "viewState", "source": self.source, "active": active, "reason": reason}))
