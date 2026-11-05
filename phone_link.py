"""Kai's phone link: the Android app as a remote control, over the local network.

Protocol v1 of Coucou's Android link (docs/ANDROID_LINK.md in Coucou), so the
same rules hold:

- TCP then TLS with a self-signed certificate made once; the phone pins its
  SHA-256 from the pairing QR code, no certificate authority, no hostname.
- One JSON object per line, at most 64 KiB.
- Pairing: kai://pair?v=1&host&port&fp&token&name. The token is the shared
  secret; "Pair again" replaces it and drops the phone that had the old one.
- The phone sees the agents' state, permission requests and Claude Code's
  questions, and answers them. "Allow" needs the phone's screen lock (the phone
  enforces it); a command cut to 500 characters can only be denied.
- Off by default. While off nothing listens. Only peers on the local network
  are served, at most 8 connections, 10 s to say hello.

The certificate's key and the token are sealed to this Windows account (DPAPI),
like Kai's other secrets. Runs in the main process, next to the hook pipe.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import ssl
import threading
import time
import urllib.parse

PORT = 47821
PROTOCOL = 1
MAX_LINE = 64 * 1024
MAX_CONNECTIONS = 8
HELLO_TIMEOUT = 10.0
IDLE_TIMEOUT = 20 * 60.0
APPROVAL_TTL = 115.0
MAX_COMMAND = 500
CLAUDE_PILL = "integration_claude"
# Optional features this computer can offer a phone that asks for them.
CAPS = ("answers", "details", "usage")

_lock = threading.Lock()
_server: "_Server | None" = None
# Called with (request_id, word) when a phone answers; set by agents.py.
decide = None


def _log(message: str) -> None:
    try:
        from agents import _log as log

        log("telefon: " + message)
    except Exception:
        pass


# ── Identity: the certificate and the pairing token ──────────────────────────


def _store_path() -> str:
    from settings import v2_file

    return v2_file("phone_link.json")


def _load_store() -> dict:
    try:
        with open(_store_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_store(data: dict) -> None:
    path = _store_path()
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(path + ".tmp", path)


def _identity() -> tuple[str, str, str]:
    """(certificate PEM, key PEM, SHA-256 of the certificate in hex), made once."""
    from settings import _seal, _unseal

    data = _load_store()
    cert, key = data.get("cert") or "", _unseal(data.get("key") or "")
    if not cert or not key:
        cert, key = _make_certificate()
        data.update({"cert": cert, "key": _seal(key)})
        _save_store(data)
    return cert, key, _fingerprint(cert)


def _make_certificate() -> tuple[str, str]:
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Kai phone link")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=36500))
        .sign(key, hashes.SHA256())
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode("ascii"),
    )


def _fingerprint(cert_pem: str) -> str:
    der = ssl.PEM_cert_to_DER_cert(cert_pem)
    return hashlib.sha256(der).hexdigest()


def _token() -> str:
    from settings import _unseal

    return _unseal(_load_store().get("token") or "")


def lan_address() -> str:
    """This computer's address on the local network (no packet is sent)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.168.255.255", 1))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def pair_again() -> dict:
    """A new token: the phone that had the old one is dropped. Returns the pairing link."""
    from settings import _seal

    _identity()
    data = _load_store()
    data["token"] = _seal(secrets.token_urlsafe(32))
    data["paired_at"] = time.time()
    _save_store(data)
    _tell_main()
    return pairing()


def unpair() -> None:
    data = _load_store()
    data.pop("token", None)
    data.pop("paired_at", None)
    _save_store(data)
    _tell_main()


def _tell_main() -> None:
    """The link runs in the main process: a new token there drops the phone that had the old one."""
    if _server:
        _server.drop_all()
        return
    from settings import push_cmd

    push_cmd("phone")


def pairing() -> dict:
    """The pairing link and its QR code (a PNG data URI), or nothing before "Pair"."""
    token = _token()
    if not token:
        return {"link": "", "qr": ""}
    _cert, _key, fp = _identity()
    port = _server.port if _server else int(_read_status().get("port") or PORT)
    query = urllib.parse.urlencode({"v": PROTOCOL, "host": lan_address(), "port": port, "fp": fp, "token": token, "name": socket.gethostname()})
    link = f"kai://pair?{query}"
    return {"link": link, "qr": _qr(link)}


def _qr(text: str) -> str:
    import base64
    import io

    import qrcode

    image = qrcode.make(text, box_size=6, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


# ── What the phone is shown ──────────────────────────────────────────────────


class _Hub:
    """The state every phone gets: the session, the waiting requests, the plan's usage."""

    def __init__(self) -> None:
        self.session = {"pillId": CLAUDE_PILL, "agent": "Claude Code", "state": "idle", "statusText": "", "stepIndex": 0, "stepCount": 0, "updatedAt": _ms()}
        self.steps: list[str] = []
        self.final_line = ""
        self.project = ""
        # fingerprint -> {request_id, line, created, truncated, questions (or None)}
        self.pending: dict[str, dict] = {}
        self.usage_line = ""

    def sessions_line(self, details: bool) -> str:
        session = dict(self.session)
        if details:
            if self.steps:
                session["steps"] = [s[:200] for s in self.steps[-20:]]
            if self.final_line:
                session["finalLine"] = self.final_line[:200]
            if self.project:
                session["project"] = self.project[:64]
            session["color"] = "#35B8FF"
        return json.dumps({"type": "sessions", "sessions": [session]}, ensure_ascii=False)


def _ms() -> int:
    return int(time.time() * 1000)


def _target(tool: str, data: dict) -> str:
    for key in ("command", "file_path", "notebook_path", "url", "path", "pattern", "query", "description"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return tool


def _questions(data: dict) -> list[dict] | None:
    """Claude Code's questions in the protocol's shape, or None when one cannot be sent whole."""
    items = data.get("questions")
    if not isinstance(items, list) or not 1 <= len(items) <= 4:
        return None
    out = []
    for item in items:
        if not isinstance(item, dict):
            return None
        question = str(item.get("question") or "")
        options = item.get("options") if isinstance(item.get("options"), list) else []
        labels = [str(o.get("label") or "") for o in options if isinstance(o, dict)]
        if not question or len(question) > 500 or not 1 <= len(options) <= 8 or len(set(labels)) != len(labels):
            return None
        shaped = []
        for option in options:
            label, description = str(option.get("label") or ""), str(option.get("description") or "")
            if not label or len(label) > 120 or len(description) > 300:
                return None
            shaped.append({"label": label, "description": description})
        out.append({"question": question, "multiSelect": bool(item.get("multiSelect")), "options": shaped})
    return out


def _fp(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


# ── The server ───────────────────────────────────────────────────────────────


class _Conn:
    def __init__(self, sock: ssl.SSLSocket, address: str) -> None:
        self.sock = sock
        self.address = address
        self.caps: set[str] = set()
        self.ready = False
        self._send_lock = threading.Lock()

    def send(self, line: str) -> bool:
        try:
            with self._send_lock:
                self.sock.sendall(line.encode("utf-8") + b"\n")
            return True
        except OSError:
            return False

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class _Server:
    def __init__(self) -> None:
        self.hub = _Hub()
        self.conns: list[_Conn] = []
        self.port = PORT
        self._stop = False
        self._listener: socket.socket | None = None

    # The listener ---------------------------------------------------------

    def start(self) -> None:
        cert, key, _fp_hex = _identity()
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        # load_cert_chain only reads files: the key is on disk for the moment it takes, then gone.
        import tempfile

        folder = tempfile.mkdtemp(prefix="kai-link-")
        try:
            cert_path, key_path = os.path.join(folder, "c.pem"), os.path.join(folder, "k.pem")
            with open(cert_path, "w", encoding="ascii") as handle:
                handle.write(cert)
            with open(key_path, "w", encoding="ascii") as handle:
                handle.write(key)
            self.context.load_cert_chain(cert_path, key_path)
        finally:
            for name in ("c.pem", "k.pem"):
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass
            try:
                os.rmdir(folder)
            except OSError:
                pass
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("0.0.0.0", PORT))
        except OSError:
            listener.bind(("0.0.0.0", 0))
        self.port = listener.getsockname()[1]
        listener.listen(8)
        listener.settimeout(1.0)
        self._listener = listener
        threading.Thread(target=self._accept, name="kai-phone", daemon=True).start()
        threading.Thread(target=self._tick, name="kai-phone-tick", daemon=True).start()
        _log(f"dinliyor, port {self.port}")

    def stop(self) -> None:
        self._stop = True
        self.drop_all()
        if self._listener:
            try:
                self._listener.close()
            except OSError:
                pass

    def drop_all(self) -> None:
        with _lock:
            conns, self.conns = self.conns, []
        for conn in conns:
            conn.close()

    def _accept(self) -> None:
        while not self._stop:
            try:
                raw, peer = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            address = peer[0]
            # Only the local network: nobody from outside is even read from.
            try:
                ip = ipaddress.ip_address(address)
                local = ip.is_private or ip.is_loopback or ip.is_link_local
            except ValueError:
                local = False
            with _lock:
                full = len(self.conns) >= MAX_CONNECTIONS
                waiting_here = sum(1 for c in self.conns if c.address == address and not c.ready)
            if not local or full or waiting_here >= 2:
                raw.close()
                continue
            threading.Thread(target=self._serve, args=(raw, address), daemon=True).start()

    # One phone --------------------------------------------------------------

    def _serve(self, raw: socket.socket, address: str) -> None:
        raw.settimeout(HELLO_TIMEOUT)
        try:
            sock = self.context.wrap_socket(raw, server_side=True)
        except (OSError, ssl.SSLError):
            raw.close()
            return
        conn = _Conn(sock, address)
        with _lock:
            self.conns.append(conn)
        try:
            reader = sock.makefile("rb")
            hello = self._read(reader)
            if not self._welcome(conn, hello):
                return
            sock.settimeout(IDLE_TIMEOUT)
            while not self._stop:
                message = self._read(reader)
                if message is None:
                    return
                self._handle(conn, message)
        except (OSError, ssl.SSLError, ValueError):
            pass
        finally:
            with _lock:
                if conn in self.conns:
                    self.conns.remove(conn)
            conn.close()
            if conn.ready:
                _write_status()

    @staticmethod
    def _read(reader) -> dict | None:
        line = reader.readline(MAX_LINE + 1)
        if not line or len(line) > MAX_LINE:
            return None
        try:
            message = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        return message if isinstance(message, dict) else None

    def _welcome(self, conn: _Conn, hello: dict | None) -> bool:
        token = _token()
        if not hello or hello.get("type") != "hello" or hello.get("v") != PROTOCOL:
            conn.send(json.dumps({"type": "error", "code": "protocol", "message": "expected hello v1"}))
            return False
        if not token or not hmac.compare_digest(str(hello.get("token") or ""), token):
            # A wrong token costs the caller a pause, and is never let in.
            time.sleep(1.0)
            conn.send(json.dumps({"type": "error", "code": "auth", "message": "not paired"}))
            _log(f"eşleşmemiş bir cihaz geri çevrildi ({conn.address})")
            return False
        from settings import Settings

        offered = set(_offered(Settings()))
        asked = {str(c) for c in hello.get("caps") or [] if isinstance(c, str)}
        conn.caps = offered & asked
        welcome = {"type": "welcome", "v": PROTOCOL, "desktop": socket.gethostname(), "os": "windows"}
        if conn.caps:
            welcome["caps"] = sorted(conn.caps)
        conn.send(json.dumps(welcome))
        conn.ready = True
        _write_status()
        _log(f"bağlandı: {str(hello.get('device') or 'telefon')[:40]}")
        conn.send(self.hub.sessions_line("details" in conn.caps))
        for item in list(self.hub.pending.values()):
            if item["questions"] is None or "answers" in conn.caps:
                conn.send(item["line"])
        if "usage" in conn.caps and self.hub.usage_line:
            conn.send(self.hub.usage_line)
        return True

    def _handle(self, conn: _Conn, message: dict) -> None:
        kind = message.get("type")
        if kind == "ping":
            conn.send('{"type":"pong"}')
        elif kind == "decision":
            item = self.hub.pending.get(str(message.get("fingerprint") or ""))
            word = message.get("decision")
            if not item or item["questions"] is not None or word not in ("allow", "deny"):
                return
            if word == "allow" and item["truncated"]:
                return  # only the computer can allow a command the phone did not see whole
            self._apply(item, word)
        elif kind == "answer" and "answers" in conn.caps:
            item = self.hub.pending.get(str(message.get("fingerprint") or ""))
            if not item or item["questions"] is None:
                return
            answers = _build_answers(item["questions"], message.get("picks"))
            if answers is not None:
                self._apply(item, json.dumps({"answers": answers}, ensure_ascii=False))

    def _apply(self, item: dict, word: str) -> None:
        if time.time() - item["created"] > APPROVAL_TTL:
            return
        _log("telefondan cevap geldi")
        if decide:
            decide(item["request_id"], word)

    # Broadcasting -----------------------------------------------------------

    def broadcast(self, line: str, need: str | None = None) -> None:
        with _lock:
            conns = [c for c in self.conns if c.ready and (need is None or need in c.caps)]
        for conn in conns:
            if not conn.send(line):
                conn.close()

    def push_sessions(self) -> None:
        with _lock:
            conns = [c for c in self.conns if c.ready]
        for conn in conns:
            conn.send(self.hub.sessions_line("details" in conn.caps))

    def _tick(self) -> None:
        """Expired requests go, and the plan's usage follows its changes."""
        while not self._stop:
            time.sleep(5)
            now = time.time()
            for fp, item in list(self.hub.pending.items()):
                if now - item["created"] > APPROVAL_TTL:
                    self.resolved_fp(fp)
            try:
                line = _usage_line()
            except Exception:
                line = ""
            if line and line != self.hub.usage_line:
                self.hub.usage_line = line
                self.broadcast(line, need="usage")

    def resolved_fp(self, fp: str) -> None:
        if self.hub.pending.pop(fp, None) is not None:
            self.broadcast(json.dumps({"type": "approvalResolved", "fingerprint": fp}))


def _build_answers(items: list[dict], picks) -> dict | None:
    """The picks checked against what was asked: one list per question, labels exactly as offered."""
    if not isinstance(picks, list) or len(picks) != len(items):
        return None
    out = {}
    for item, chosen in zip(items, picks):
        labels = [o["label"] for o in item["options"]]
        if not isinstance(chosen, list) or not chosen or len(set(chosen)) != len(chosen):
            return None
        if not item["multiSelect"] and len(chosen) != 1:
            return None
        if any(not isinstance(c, str) or c not in labels for c in chosen):
            return None
        out[item["question"]] = chosen if item["multiSelect"] else chosen[0]
    return out


def _usage_line() -> str:
    import usage

    snap = usage.snapshot() or {}
    limits = snap.get("limits") or {}
    claude = {}
    for name, key in (("five_hour", "fiveHour"), ("seven_day", "sevenDay")):
        window = limits.get(name)
        if isinstance(window, dict) and window.get("used") is not None:
            claude[key] = {"pct": max(0, min(100, round(float(window["used"])))), "resetsAt": int(float(window.get("resets") or 0) * 1000)}
    if not claude:
        return json.dumps({"type": "usage"})
    claude["updatedAt"] = _ms()
    return json.dumps({"type": "usage", "claude": claude})


def _offered(settings) -> list[str]:
    caps = ["usage", "details"]
    if getattr(settings, "phone_answers", True):
        caps.append("answers")
    return caps


# ── What Kai tells the link (agents.py) ─────────────────────────────────────


def on_hook(payload: dict) -> None:
    """A Claude Code event: the phone's session follows it."""
    server = _server
    if not server:
        return
    hub = server.hub
    event = str(payload.get("hook_event_name") or "")
    tool = str(payload.get("tool_name") or "")
    session = hub.session
    cwd = str(payload.get("cwd") or "")
    if cwd:
        hub.project = os.path.basename(cwd.rstrip("\\/"))
    if event == "UserPromptSubmit":
        session.update(state="working", statusText="Çalışıyor", stepIndex=0, stepCount=0)
        hub.steps, hub.final_line = [], ""
    elif event == "PreToolUse":
        data = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
        step = f"{tool}: {os.path.basename(_target(tool, data))[:120]}" if tool else "Çalışıyor"
        hub.steps.append(step)
        session.update(state="working", statusText=step[:80], stepIndex=len(hub.steps), stepCount=len(hub.steps))
    elif event == "Stop":
        if payload.get("queued_next"):
            session.update(state="working", statusText="Sıradaki işe geçti")
        else:
            final = " ".join(str(payload.get("last_assistant_message") or "").split())
            hub.final_line = final[:200]
            session.update(state="finished", statusText="Bitti")
    elif event == "StopFailure":
        session.update(state="error", statusText="Hata")
    elif event == "SessionEnd":
        session.update(state="idle", statusText="")
    else:
        return
    session["updatedAt"] = _ms()
    server.push_sessions()


def on_request(request_id: str, payload: dict) -> None:
    """A permission request or a question waits on the island: the phones get it too."""
    server = _server
    if not server:
        return
    tool = str(payload.get("tool_name") or "Tool")
    data = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    session_id = str(payload.get("session_id") or "")
    questions = _questions(data) if tool == "AskUserQuestion" else None
    if tool == "AskUserQuestion" and questions is None:
        return  # cannot be sent whole: it stays on the computer
    if questions is not None:
        fp = _fp(CLAUDE_PILL, session_id, json.dumps([q["question"] for q in questions], ensure_ascii=False), request_id)
        line = json.dumps({"type": "question", "pillId": CLAUDE_PILL, "fingerprint": fp, "createdAt": _ms(), "questions": questions}, ensure_ascii=False)
        truncated = False
    else:
        command = _target(tool, data)
        truncated = len(command) > MAX_COMMAND
        command = command[:MAX_COMMAND]
        fp = _fp(CLAUDE_PILL, session_id, tool, command, request_id)
        line = json.dumps({"type": "approval", "pillId": CLAUDE_PILL, "fingerprint": fp, "tool": tool, "command": command, "truncated": truncated, "createdAt": _ms()}, ensure_ascii=False)
    server.hub.pending[fp] = {"request_id": request_id, "line": line, "created": time.time(), "truncated": truncated, "questions": questions}
    server.hub.session.update(state="question" if questions else "approval", statusText="Soru soruyor" if questions else "İzin istiyor", updatedAt=_ms())
    server.push_sessions()
    server.broadcast(line, need="answers" if questions else None)


def on_resolved(request_id: str) -> None:
    """Answered on the island, by voice, on a phone, or given up: the phones take it down."""
    server = _server
    if not server:
        return
    for fp, item in list(server.hub.pending.items()):
        if item["request_id"] == request_id:
            server.resolved_fp(fp)
    if server.hub.session["state"] in ("approval", "question") and not server.hub.pending:
        server.hub.session.update(state="working", statusText="Çalışıyor", updatedAt=_ms())
        server.push_sessions()


# ── On and off ──────────────────────────────────────────────────────────────


def apply(settings) -> None:
    """Started or stopped with the setting (Kai window › Phone); off by default."""
    global _server
    want = bool(getattr(settings, "phone_link", False))
    with _lock:
        running = _server
    if want and not running:
        server = _Server()
        try:
            server.start()
        except Exception as exc:
            _log(f"başlamadı: {type(exc).__name__}: {exc}")
            return
        _server = server
    elif not want and running:
        _server = None
        running.stop()
        _log("kapandı")
    _write_status()


def _status_path() -> str:
    from settings import v2_file

    return v2_file("phone_status.json")


def _write_status() -> None:
    """For the Kai window, another process: on or off, the port, how many phones are in."""
    server = _server
    with _lock:
        phones = sum(1 for c in server.conns if c.ready) if server else 0
    try:
        with open(_status_path() + ".tmp", "w", encoding="utf-8") as handle:
            json.dump({"on": server is not None, "port": server.port if server else PORT, "phones": phones}, handle)
        os.replace(_status_path() + ".tmp", _status_path())
    except OSError:
        pass


def _read_status() -> dict:
    try:
        with open(_status_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def status() -> dict:
    """What the Kai window shows: from the main process's status file."""
    shown = _read_status()
    return {"on": bool(shown.get("on")), "paired": bool(_load_store().get("token")), "phones": int(shown.get("phones") or 0), "port": int(shown.get("port") or PORT)}
