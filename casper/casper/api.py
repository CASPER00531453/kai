"""Arayüzün (HTML/JS) çağırdığı Python yöntemleri. pywebview js_api olarak verilir.

Her yöntem JSON'a çevrilebilir bir şey döndürür. Hatalar {"error": "..."} olur;
arayüz bunları kırmızı bir uyarı olarak gösterir.
"""

from __future__ import annotations

import functools
import os
import secrets as pysecrets
import subprocess
import sys
import threading
import time
import traceback

from . import __version__, brain, db, importers, llm, metrics, paths, secrets


def safe(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except llm.LLMError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            traceback.print_exc()
            return {"error": f"{type(exc).__name__}: {exc}"}

    return wrapper


class Api:
    def __init__(self, app=None) -> None:
        self._app = app  # casper.app.CasperApp: pencereler ve gözcü
        self._previews: dict[str, dict] = {}
        self._lock = threading.Lock()

    # --- genel ----------------------------------------------------------------

    @safe
    def state(self):
        settings = db.all_settings()
        settings.pop("api_key", None)
        return {
            "version": __version__,
            "has_key": secrets.has_api_key(),
            "settings": settings,
            "people": self.list_people(),
            "watch": self._app.watcher.status() if self._app else {"running": False},
            "screens": self._app.screens() if self._app else [],
            "data_dir": paths.data_dir(),
            "platform": sys.platform,
        }

    @safe
    def save_settings(self, values: dict):
        for key, value in (values or {}).items():
            if key in db.DEFAULTS and key != "api_key":
                db.set_setting(key, value)
        if self._app and "watch_overlay_screen" in values:
            self._app.place_overlay()
        return {"ok": True}

    @safe
    def save_api_key(self, key: str):
        secrets.save_api_key(key or "")
        return {"ok": True, "has_key": secrets.has_api_key()}

    @safe
    def test_api(self):
        reply = llm.ask(
            model_key="model_chat",
            system="Kısa cevap ver.",
            messages=[{"role": "user", "content": "Sadece 'hazırım' yaz."}],
            effort="low",
            max_tokens=2000,
        )
        return {"ok": True, "reply": reply}

    # --- kişiler --------------------------------------------------------------

    @safe
    def list_people(self):
        return db.people()

    @safe
    def get_person(self, pid: int):
        p = db.person(int(pid))
        if not p:
            return {"error": "Kişi bulunamadı."}
        msgs = db.messages_for(p["id"])
        p["metrics"] = metrics.compute(msgs) if msgs else {"mesaj": 0}
        p["imports"] = db.imports_for(p["id"])
        p["analyses"] = db.analyses_for(p["id"])
        p["platform_counts"] = db.rows(
            "SELECT platform, COUNT(*) AS n FROM messages WHERE person_id = ? GROUP BY platform", (p["id"],)
        )
        p["recent"] = db.messages_for(p["id"], limit=40)
        return p

    @safe
    def create_person(self, name: str, relation: str = "", notes: str = ""):
        name = (name or "").strip()
        if not name:
            return {"error": "İsim boş olamaz."}
        return {"id": db.create_person(name, relation, notes)}

    @safe
    def update_person(self, pid: int, data: dict):
        pid = int(pid)
        db.update_person(pid, **{k: v for k, v in data.items() if k in ("name", "relation", "notes", "card")})
        if "aliases" in data:
            aliases = [a for a in data["aliases"] if (a.get("name") or "").strip()]
            name = (data.get("name") or db.person(pid)["name"]).strip()
            if not any(a["name"].strip() == name for a in aliases):
                aliases.append({"platform": "", "name": name})
            db.set_aliases(pid, aliases)
        return {"ok": True}

    @safe
    def delete_person(self, pid: int):
        db.delete_person(int(pid))
        return {"ok": True}

    @safe
    def delete_messages(self, pid: int, platform: str = ""):
        db.delete_messages(int(pid), platform or None)
        return {"ok": True}

    # --- içe aktarma ----------------------------------------------------------

    @safe
    def pick_files(self, platform: str):
        if not self._app:
            return {"error": "Pencere yok."}
        kinds = {
            "whatsapp": ("WhatsApp dışa aktarımı (*.txt;*.zip)", "Tüm dosyalar (*.*)"),
            "instagram": ("Instagram paketi (*.zip;*.json)", "Tüm dosyalar (*.*)"),
            "discord": ("Discord paketi (*.zip;*.json;*.csv)", "Tüm dosyalar (*.*)"),
        }
        return {"paths": self._app.open_files(kinds.get(platform, ("Tüm dosyalar (*.*)",)))}

    @safe
    def pick_folder(self):
        if not self._app:
            return {"error": "Pencere yok."}
        return {"paths": self._app.open_folder()}

    @safe
    def import_preview(self, pid: int, platform: str, paths_: list[str]):
        if not paths_:
            return {"error": "Dosya seçilmedi."}
        p = db.person(int(pid))
        if not p:
            return {"error": "Kişi bulunamadı."}
        threads = importers.parse(platform, list(paths_))
        if not threads:
            return {"error": "Bu dosyalarda okunabilir mesaj bulunamadı. Doğru platformu ve biçimi (Instagram için JSON) seçtiğinden emin ol."}
        their = [a["name"] for a in p["aliases"]] + [p["name"]]
        my_names = db.get_setting("my_names") or []
        token = pysecrets.token_hex(8)
        with self._lock:
            self._previews = {token: {"platform": platform, "threads": threads, "paths": paths_}}
        summaries = []
        for t in threads:
            s = t.summary()
            s["guess_me"] = importers.guess_me(t, my_names, their)
            summaries.append(s)
        return {
            "token": token,
            "threads": summaries,
            "best": importers.best_thread(threads, their),
        }

    @safe
    def import_commit(self, token: str, pid: int, thread_ids: list[str], me_sender: str):
        with self._lock:
            preview = self._previews.get(token)
        if not preview:
            return {"error": "Önizleme süresi doldu, dosyayı yeniden seç."}
        pid = int(pid)
        platform = preview["platform"]
        added = total = 0
        my_names = list(db.get_setting("my_names") or [])
        for t in preview["threads"]:
            if t.id not in thread_ids:
                continue
            msgs = []
            for m in t.messages:
                from_me = m.get("from_me")
                if from_me is None:
                    from_me = importers.norm(m["sender"]) == importers.norm(me_sender)
                msgs.append({**m, "from_me": bool(from_me)})
            total += len(msgs)
            n = db.add_messages(pid, platform, t.title, msgs)
            added += n
            # Karşı tarafın görünen adını kişiye bağla: gözcü onu ekranda tanısın.
            for sender in t.senders():
                if importers.norm(sender) != importers.norm(me_sender) and sender != importers.ME_SENDER:
                    if len(t.senders()) <= 2:
                        db.add_alias(pid, platform, sender)
            db.log_import(pid, platform, ", ".join(os.path.basename(x) for x in preview["paths"]) + f" › {t.title}", n)
        if me_sender and me_sender != importers.ME_SENDER and me_sender not in my_names:
            my_names.append(me_sender)
            db.set_setting("my_names", my_names)
        with self._lock:
            self._previews.pop(token, None)
        return {"added": added, "total": total, "skipped": total - added}

    # --- Casper ---------------------------------------------------------------

    @safe
    def analyze(self, pid: int):
        return {"text": brain.analyze_person(int(pid))}

    @safe
    def chat_send(self, text: str):
        text = (text or "").strip()
        if not text:
            return {"error": "Boş mesaj."}
        return {"reply": brain.chat(text)}

    @safe
    def chat_history(self):
        return db.recent_chat(200)

    @safe
    def chat_clear(self):
        db.clear_chat()
        return {"ok": True}

    @safe
    def facts(self):
        return db.facts()

    @safe
    def add_fact(self, text: str):
        db.add_fact(text or "")
        return {"ok": True}

    @safe
    def delete_fact(self, fid: int):
        db.delete_fact(int(fid))
        return {"ok": True}

    # --- gözcü ----------------------------------------------------------------

    @safe
    def watch_start(self):
        if not secrets.has_api_key():
            return {"error": "Önce Ayarlar'dan Claude API anahtarını ekle."}
        self._app.start_watch()
        return self._app.watcher.status()

    @safe
    def watch_stop(self):
        self._app.stop_watch()
        return self._app.watcher.status()

    @safe
    def watch_recent(self):
        start = time.time() - 6 * 3600
        return [w for w in db.watch_between(start, time.time() + 1) if w["comment"]][-50:]

    @safe
    def overlay_toggle(self, show: bool):
        self._app.show_overlay(bool(show))
        return {"ok": True}

    # --- gün sonu -------------------------------------------------------------

    @safe
    def daily_now(self):
        return {"text": brain.daily_summary()}

    @safe
    def summaries(self):
        return db.summaries()

    # --- dosyalar ve temizlik -------------------------------------------------

    @safe
    def open_folder(self, which: str = "data"):
        target = paths.user_knowledge_dir() if which == "knowledge" else paths.data_dir()
        if os.name == "nt":
            os.startfile(target)  # noqa: S606 - kullanıcının kendi klasörü
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return {"ok": True, "path": target}

    @safe
    def wipe(self, confirm: str):
        if confirm != "SİL":
            return {"error": "Onay için SİL yaz."}
        if self._app:
            self._app.stop_watch()
        db.wipe_everything()
        return {"ok": True}
