"""Small things Kai does on request, shared by voice (AltGr, OK Kai) and the typed chat.

Email: with an address and an app password saved (Kai app › Integrations), Kai
shows the email and asks "Göndereyim mi?"; it is sent only when the very next
thing the user says is a yes. Anything else drops it. Without them Kai opens a
draft (mail app, else Gmail) and says the user has to press Send. The waiting
email is kept in a file because voice and the typed chat run in different
processes.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import webbrowser

PENDING_SECONDS = 300
YES = {"evet", "gönder", "gonder", "gönderebilirsin", "yolla", "tamam", "olur", "onaylıyorum", "onayliyorum", "yes", "send", "ok", "okay", "sure", "yep"}
NO = {"hayır", "hayir", "iptal", "vazgeç", "vazgec", "gönderme", "gonderme", "dur", "bekle", "no", "cancel", "stop", "don't", "dont"}
DRAFT = {"taslak", "düzenle", "duzenle", "draft", "edit"}

# address domain -> (SMTP server, port; 465 is SSL, 587 is STARTTLS)
SERVERS = {
    "gmail.com": ("smtp.gmail.com", 465),
    "googlemail.com": ("smtp.gmail.com", 465),
    "outlook.com": ("smtp-mail.outlook.com", 587),
    "hotmail.com": ("smtp-mail.outlook.com", 587),
    "live.com": ("smtp-mail.outlook.com", 587),
    "yandex.com": ("smtp.yandex.com", 465),
    "yandex.com.tr": ("smtp.yandex.com", 465),
    "icloud.com": ("smtp.mail.me.com", 587),
    "me.com": ("smtp.mail.me.com", 587),
    "yahoo.com": ("smtp.mail.yahoo.com", 465),
}

EMAIL_WORDS = ("e-posta", "eposta", "e posta", "mail", "email", "ileti gönder", "alıcı", "konu:", "konusu")
STRIPE_WORDS = ("stripe",)


def wants_email(text: str) -> bool:
    folded = text.lower()
    return any(w in folded for w in EMAIL_WORDS)


def wants_stripe(text: str) -> bool:
    return any(w in text.lower() for w in STRIPE_WORDS)


def _mail_app() -> bool:
    """True when Windows has an app picked for mailto: links."""
    try:
        import winreg

        path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\mailto\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            prog, _ = winreg.QueryValueEx(key, "ProgId")
            return bool(prog)
    except OSError:
        return False


def mail_ready(settings) -> bool:
    return bool(getattr(settings, "mail_address", "") and getattr(settings, "mail_password", ""))


def _pending_path() -> str:
    from settings import v2_file

    return v2_file("pending_mail.json")


def _set_pending(mail: dict | None) -> None:
    path = _pending_path()
    if mail is None:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    tmp = path + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump({**mail, "made": time.time()}, handle, ensure_ascii=False)
    os.replace(tmp, path)


def _pending() -> dict | None:
    try:
        with open(_pending_path(), encoding="utf-8") as handle:
            mail = json.load(handle)
    except (OSError, ValueError):
        return None
    if time.time() - float(mail.get("made") or 0) > PENDING_SECONDS:
        _set_pending(None)
        return None
    return mail


def send_mail(settings, to: str, subject: str, body: str) -> None:
    """Sends through the user's own mailbox. Raises RuntimeError with a sentence the user can act on."""
    import smtplib
    import ssl
    from email.message import EmailMessage

    sender = settings.mail_address.strip()
    host, port = SERVERS.get(sender.rsplit("@", 1)[-1].lower(), ("", 0))
    if getattr(settings, "mail_server", ""):
        host, _, raw = settings.mail_server.partition(":")
        port = int(raw or 465)
    if not host:
        raise RuntimeError("Bu e-posta sağlayıcısının sunucusunu bilmiyorum; Entegrasyonlar'da sunucuyu yaz (ör. smtp.alanadi.com:465).")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, to, subject
    message.set_content(body)
    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
                smtp.login(sender, settings.mail_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(sender, settings.mail_password)
                smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError("Şifre kabul edilmedi. Normal şifren değil, uygulama şifresi lazım (Gmail: myaccount.google.com/apppasswords).") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise RuntimeError(f"E-posta gönderilemedi: {exc}") from exc


def _words(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.replace("İ", "i").replace("I", "ı").lower())


def confirm(settings, text: str) -> str | None:
    """The reply to "Göndereyim mi?". None when no email is waiting; anything but a yes or a draft drops it."""
    mail = _pending()
    if not mail:
        return None
    turkish = getattr(settings, "language", "tr") == "tr"
    words = _words(text)
    _set_pending(None)
    if len(words) <= 6 and any(w in DRAFT for w in words):
        return draft_email(mail, turkish, ask=False)
    if len(words) > 6 or any(w in NO for w in words) or not any(w in YES for w in words):
        return "Tamam, göndermedim." if turkish else "OK, not sent."
    try:
        send_mail(settings, mail["to"], mail["subject"], mail["body"])
    except RuntimeError as exc:
        return str(exc)
    return f"Gönderdim: {mail['to']}, konu «{mail['subject']}»." if turkish else f"Sent to {mail['to']}, subject «{mail['subject']}»."


def draft_email(decision: dict, turkish: bool = True, settings=None, ask: bool = True) -> str:
    to = str(decision.get("to") or "").strip()
    subject = str(decision.get("subject") or "").strip()
    body = str(decision.get("body") or "").strip()
    found = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", to)
    address = found.group(0) if found else ""
    if ask and address and settings is not None and mail_ready(settings):
        _set_pending({"to": address, "subject": subject, "body": body})
        if turkish:
            return f"Kime: {address}. Konu: {subject}. Metin: «{body}». Göndereyim mi? Evet dersen gönderirim; hayır dersen iptal, taslak dersen açarım."
        return f"To: {address}. Subject: {subject}. Text: «{body}». Shall I send it? Say yes to send, no to cancel, draft to open it."
    try:
        if _mail_app():
            query = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
            os.startfile(f"mailto:{urllib.parse.quote(address, safe='@')}?{query}")
            where = "e-posta uygulamanda" if turkish else "in your mail app"
        else:
            query = urllib.parse.urlencode({"view": "cm", "fs": "1", "to": address, "su": subject, "body": body}, quote_via=urllib.parse.quote)
            webbrowser.open(f"https://mail.google.com/mail/?{query}")
            where = "Gmail'de" if turkish else "in Gmail"
    except Exception:
        return "E-posta taslağını açamadım." if turkish else "I couldn't open an email draft."
    missing = "" if address else (f"; {to} için adresi sen yaz" if turkish else f"; add the address for {to}")
    if turkish:
        return f"Taslağı {where} açtım{missing}. Ben göndermedim, Gönder'e sen bas."
    return f"The draft is open {where}{missing}. I didn't send it: press Send yourself."


def stripe_today(key: str, turkish: bool = True) -> str:
    import services

    if not key:
        return "Stripe anahtarı yok; Kai uygulamasında Entegrasyonlar'dan ekleyebilirsin." if turkish else "No Stripe key; add one under Integrations in the Kai app."
    got = services.stripe_today(key)
    if got is None:
        return "Stripe'a ulaşamadım." if turkish else "I couldn't reach Stripe."
    cents, currency, count = got
    amount = f"{cents / 100:,.2f} {currency.upper()}"
    return f"Bugün {count} ödemeyle {amount} kazandın." if turkish else f"Today: {amount} from {count} payments."


def before(settings, text: str) -> str | None:
    """Checked first, for voice and typed chat alike: a reply to a waiting email, then the calendar."""
    answer = confirm(settings, text)
    if answer:
        return answer
    import web

    # Before "open an app": "YouTube'da Tarkan aç" is a video, not a program called that.
    if web.wants_web(text):
        from brain import decide

        try:
            decision = decide(settings, text)
        except Exception:
            decision = {}
        if decision.get("do") == "web":
            return web.act(decision, getattr(settings, "language", "tr") == "tr")
    import kaicalendar

    cal = kaicalendar.intent(text)
    if cal and cal["act"] == "list":
        return kaicalendar.describe_day(settings, cal["day"])
    if cal and cal["act"] == "add":
        return kaicalendar.add_event(settings, cal["title"], cal["due"])
    return None


def typed_request(settings, text: str) -> str | None:
    """For the typed chat: an email or a Stripe question is done, not just talked about."""
    import web

    if not (wants_email(text) or wants_stripe(text) or web.wants_web(text)):
        return None
    from brain import decide

    try:
        decision = decide(settings, text)
    except Exception:
        return None
    turkish = getattr(settings, "language", "tr") == "tr"
    if decision.get("do") == "email":
        return draft_email(decision, turkish, settings)
    if decision.get("do") == "stripe":
        return stripe_today(getattr(settings, "stripe_key", ""), turkish)
    if decision.get("do") == "web":
        return web.act(decision, turkish)
    return None
