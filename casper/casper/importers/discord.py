"""Discord veri paketi (package.zip ya da açılmış klasör).

Messages/index.json kanal numaralarını adlara bağlar. Her kanal Messages/c<numara>/
altında messages.json (yeni) ya da messages.csv (eski) olarak durur.
Pakette SADECE senin gönderdiğin mesajlar vardır.
"""

from __future__ import annotations

import csv
import io
import json
import posixpath
from datetime import datetime

from . import ME_SENDER, Thread, read_sources


def _wanted(name: str) -> bool:
    base = posixpath.basename(name).lower()
    return base in ("messages.json", "messages.csv", "index.json", "channel.json")


def _ts(value: str) -> float:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(value[:26], fmt).timestamp()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _channel_title(channel: dict) -> str:
    recipients = channel.get("recipients")
    name = channel.get("name") or ""
    guild = (channel.get("guild") or {}).get("name") or ""
    if guild:
        return f"{guild} #{name}" if name else guild
    if name:
        return name
    if isinstance(recipients, list) and recipients:
        return "DM " + ", ".join(str(r) for r in recipients)
    return ""


def parse_paths(paths: list[str]) -> list[Thread]:
    files = read_sources(paths, _wanted)
    index: dict[str, str] = {}
    channels: dict[str, dict] = {}
    for name, data in files:
        base = posixpath.basename(name).lower()
        if base == "index.json":
            try:
                index.update({str(k): str(v) for k, v in json.loads(data.decode("utf-8")).items()})
            except (ValueError, AttributeError):
                pass
        elif base == "channel.json":
            try:
                channels[posixpath.dirname(name)] = json.loads(data.decode("utf-8"))
            except ValueError:
                pass

    threads: list[Thread] = []
    for name, data in files:
        base = posixpath.basename(name).lower()
        if base not in ("messages.json", "messages.csv"):
            continue
        folder = posixpath.dirname(name)
        cid = posixpath.basename(folder).lstrip("c") or folder
        channel = channels.get(folder, {})
        title = index.get(cid) or _channel_title(channel) or f"Kanal {cid}"
        thread = Thread(id=cid, title=title, platform="discord", only_mine=True)
        text = data.decode("utf-8-sig", errors="replace")
        if base == "messages.json":
            try:
                items = json.loads(text)
            except ValueError:
                items = []
            for m in items if isinstance(items, list) else []:
                content = (m.get("Contents") or "").strip()
                if not content and m.get("Attachments"):
                    content = "[medya]"
                ts = _ts(m.get("Timestamp", ""))
                if content and ts:
                    thread.messages.append({"sender": ME_SENDER, "ts": ts, "text": content, "from_me": True})
        else:
            for m in csv.DictReader(io.StringIO(text)):
                content = (m.get("Contents") or "").strip() or ("[medya]" if m.get("Attachments") else "")
                ts = _ts(m.get("Timestamp", ""))
                if content and ts:
                    thread.messages.append({"sender": ME_SENDER, "ts": ts, "text": content, "from_me": True})
        threads.append(thread)
    threads.sort(key=lambda t: -len(t.messages))
    return threads
