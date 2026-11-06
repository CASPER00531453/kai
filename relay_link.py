"""The phone link over the internet, through a relay on the user's own Cloudflare account.

Protocol: Coucou's relay link (docs/RELAY_LINK.md there; the Worker is server/relay).
The relay only forwards opaque frames between this computer and the paired phone:
every v1 line travels inside an end-to-end channel (HKDF-SHA-256, AES-256-GCM)
keyed by K, which only the computer and the phone hold. The relay sees neither K
nor any content.

Off unless the user picks "Cloudflare" as the way to reach the phone (Kai window ›
Phone). The LAN link stays on as the fast path at home.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import threading
import time

LABEL = b"coucou-relay/v1"  # the protocol's own constant: the phone derives the same keys from it
VERSION = 1
INIT, ACCEPT, DATA = 1, 2, 3
P2H, H2P = 1, 2
MAX_LINE = 65_536
LAST_COUNTER = 2**32 - 1


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64u(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hkdf(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt or None, info=info).derive(ikm)


def k_auth(k: bytes) -> bytes:
    return hkdf(k, b"", LABEL + b" auth", 32)


def k_join(k: bytes) -> bytes:
    return hkdf(k, b"", LABEL + b" join", 32)


def session_keys(k: bytes, n_phone: bytes, n_pc: bytes) -> tuple[bytes, bytes]:
    """(phone → computer, computer → phone)."""
    out = hkdf(k, n_phone + n_pc, LABEL + b" session", 64)
    return out[:32], out[32:]


def header(kind: int, counter: int) -> bytes:
    return struct.pack(">BBQ", VERSION, kind, counter)


def nonce(direction: int, counter: int) -> bytes:
    return bytes([direction, 0, 0, 0]) + struct.pack(">Q", counter)


def aad(room: str, direction: int, head: bytes) -> bytes:
    return LABEL + room.encode("ascii") + bytes([direction]) + head


def pad(line: bytes) -> bytes:
    body = struct.pack(">I", len(line)) + line
    size = max(128, -(-len(body) // 128) * 128)
    return body + b"\0" * (size - len(body))


def unpad(plain: bytes) -> bytes:
    if len(plain) < 4:
        raise ValueError("bad_padding")
    n = struct.unpack(">I", plain[:4])[0]
    if n > MAX_LINE or 4 + n > len(plain) or any(plain[4 + n:]):
        raise ValueError("bad_padding")
    return plain[4:4 + n]


def accept_frame(k: bytes, room: str, n_phone: bytes, n_pc: bytes) -> bytes:
    mac = hmac.new(k_auth(k), b"accept" + room.encode("ascii") + n_phone + n_pc, hashlib.sha256).digest()
    return header(ACCEPT, 0) + n_pc + mac


def check_init(k: bytes, room: str, frame: bytes) -> bytes | None:
    """The phone's nonce from a valid init frame, else None."""
    if len(frame) != 10 + 16 + 32 or frame[:10] != header(INIT, 0):
        return None
    n_phone, mac = frame[10:26], frame[26:]
    want = hmac.new(k_auth(k), b"init" + room.encode("ascii") + n_phone, hashlib.sha256).digest()
    return n_phone if hmac.compare_digest(mac, want) else None


class Channel:
    """One session's two directions, from the computer's side."""

    def __init__(self, k: bytes, room: str, n_phone: bytes, n_pc: bytes) -> None:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        p2h, h2p = session_keys(k, n_phone, n_pc)
        self.room = room
        self._in = AESGCM(p2h)
        self._out = AESGCM(h2p)
        self._next_in = 0
        self._next_out = 0
        self._lock = threading.Lock()

    def seal(self, line: bytes) -> bytes:
        with self._lock:
            counter = self._next_out
            if counter > LAST_COUNTER:
                raise ValueError("session_over")
            self._next_out += 1
        head = header(DATA, counter)
        return head + self._out.encrypt(nonce(H2P, counter), pad(line), aad(self.room, H2P, head))

    def open(self, frame: bytes) -> bytes:
        if len(frame) < 10 + 16 + 128 or frame[0] != VERSION or frame[1] != DATA:
            raise ValueError("bad_header")
        counter = struct.unpack(">Q", frame[2:10])[0]
        if counter != self._next_in:
            raise ValueError("bad_counter")
        plain = self._in.decrypt(nonce(P2H, counter), frame[10:], aad(self.room, P2H, frame[:10]))
        self._next_in += 1
        return unpad(plain)


# ── The pairing's relay secrets ──────────────────────────────────────────────


def secrets_for_link(store: dict) -> dict | None:
    """K, the room and the relay's address and access key; None when the relay is not set up."""
    from settings import _unseal

    k = _unseal(store.get("relay_k") or "")
    room = store.get("relay_room") or ""
    url = store.get("relay_url") or ""
    access = _unseal(store.get("relay_access") or "")
    if not (k and room and url and access):
        return None
    return {"k": unb64u(k), "room": room, "url": url, "access": access}


def save_relay(url: str, access: str) -> None:
    """The relay this computer uses (server/relay/deploy.ps1 calls it after deploying)."""
    import phone_link
    from settings import _seal, push_cmd

    if not url.startswith("wss://") or len(access) != 43:
        raise ValueError("a wss:// address and a 43-character access key")
    store = phone_link._load_store()
    store["relay_url"] = url.rstrip("/")
    store["relay_access"] = _seal(access)
    if not store.get("relay_room"):
        new_room(store)
    phone_link._save_store(store)
    push_cmd("phone")


def new_room(store: dict) -> None:
    """A new K and room for a new pairing: the old phone's room stays empty forever."""
    from settings import _seal

    store["relay_k"] = _seal(b64u(os.urandom(32)))
    store["relay_room"] = b64u(os.urandom(16))


# ── The client ───────────────────────────────────────────────────────────────


class RelayClient:
    """Keeps this computer in its room on the relay; one phone at a time."""

    def __init__(self, server, store: dict) -> None:
        self.server = server  # phone_link._Server: the same v1 code as a LAN connection
        self.secrets = secrets_for_link(store)
        self._stop = threading.Event()
        self._ws = None
        self.state = "off"

    def start(self) -> None:
        if self.secrets:
            threading.Thread(target=self._run, name="kai-relay", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        ws = self._ws
        if ws:
            try:
                ws.close()
            except Exception:
                pass

    def _run(self) -> None:
        import websocket

        wait = 2.0
        while not self._stop.is_set():
            s = self.secrets
            url = f"{s['url'].rstrip('/')}/v1/room/{s['room']}?role=pc"
            try:
                self.state = "connecting"
                ws = websocket.create_connection(
                    url,
                    timeout=30,
                    header=[f"Authorization: Bearer {s['access']}"],
                    subprotocols=["coucou.v1", "coucou.join." + b64u(k_join(s["k"]))],
                    enable_multithread=True,
                )
                self._ws = ws
                self.state = "online"
                wait = 2.0
                self._serve(ws)
            except Exception as exc:
                self.state = f"error: {type(exc).__name__}"
            finally:
                self._ws = None
            if self._stop.wait(wait):
                return
            wait = min(60.0, wait * 2)

    def _serve(self, ws) -> None:
        import websocket

        s = self.secrets
        channel: Channel | None = None
        conn = None
        bad = 0
        last_ping = time.monotonic()
        ws.settimeout(25)
        while not self._stop.is_set():
            try:
                opcode, data = ws.recv_data()
            except websocket.WebSocketTimeoutException:
                # The platform answers "ping" itself: cheap, and it keeps the socket alive.
                ws.send("ping")
                last_ping = time.monotonic()
                continue
            if opcode == websocket.ABNF.OPCODE_CLOSE:
                return
            if opcode == websocket.ABNF.OPCODE_TEXT:
                continue  # hints ("peer online/offline") and "pong": never trusted for anything
            if opcode != websocket.ABNF.OPCODE_BINARY or len(data) < 10:
                continue
            kind = data[1]
            if kind == INIT:
                n_phone = check_init(s["k"], s["room"], data)
                if n_phone is None:
                    bad += 1
                    if bad >= 3:
                        time.sleep(10)
                        bad = 0
                    continue
                n_pc = os.urandom(16)
                # Only the newest init is answered: a new one drops the previous session.
                if conn:
                    conn.close()
                channel = Channel(s["k"], s["room"], n_phone, n_pc)
                ws.send_binary(accept_frame(s["k"], s["room"], n_phone, n_pc))
                conn = self.server.relay_conn(lambda line, ch=channel: self._send(ws, ch, line))
            elif kind == DATA and channel and conn:
                try:
                    line = channel.open(data)
                except Exception:
                    # A fault ends the session: the phone starts again with init.
                    conn.close()
                    channel, conn = None, None
                    continue
                if not conn.feed(line):
                    channel, conn = None, None
            if time.monotonic() - last_ping > 25:
                ws.send("ping")
                last_ping = time.monotonic()

    @staticmethod
    def _send(ws, channel: "Channel", line: str) -> bool:
        try:
            ws.send_binary(channel.seal(line.encode("utf-8")))
            return True
        except Exception:
            return False
