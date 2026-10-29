"""Kai's calendar: "bugün neyim var", "yarın 3'te toplantı koy".

Events are read from the calendar's secret iCal address (Google Calendar:
Settings › the calendar › "Secret address in iCal format"; Outlook: Settings ›
Shared calendars › Publish › ICS), so no account sign-in is needed. Kai never
writes to the calendar: adding an event opens the calendar's own new-event
page filled in, and the user saves it. Kai's reminders are listed alongside,
and events that have a link are announced ten minutes before they start.
"""

from __future__ import annotations

import datetime as dt
import re
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

LEAD = 10 * 60
_cache: dict = {"url": "", "at": 0.0, "events": []}
_lock = threading.Lock()

LIST_WORDS = (
    "neyim var", "programım", "programim", "takvimimde", "takvimde ne", "takvimim", "ajandam",
    "toplantılarım", "toplantilarim", "randevularım", "randevularim", "bugün ne var", "bugun ne var",
    "yarın ne var", "yarin ne var", "my calendar", "my schedule", "what's on", "whats on",
)
CAL_WORDS = ("takvim", "toplantı", "toplanti", "randevu", "etkinlik", "görüşme", "gorusme", "calendar", "meeting")
ADD_VERBS = ("koy", "ekle", "oluştur", "olustur", "ayarla", "kaydet", "planla", "add", "schedule", "put")
FILLER = re.compile(
    r"\b(takvime|takvimime|takvimde|takvim|koy\w*|ekle\w*|oluştur\w*|olustur\w*|ayarla\w*|kaydet\w*|planla\w*|"
    r"bir|tane|lütfen|lutfen|kai|benim|bana|için|icin)\b",
    re.IGNORECASE,
)


def _fold(text: str) -> str:
    return " ".join(text.replace("İ", "i").replace("I", "ı").lower().split())


def intent(text: str) -> dict | None:
    """{'act': 'list', 'day': 0|1} or {'act': 'add', 'title', 'due'}; None when it is not about the calendar."""
    import reminders

    low = _fold(text)
    words = set(re.findall(r"\w+", low))
    adding = any(w.startswith(verb) for w in words for verb in ADD_VERBS)
    if adding and any(word in low for word in CAL_WORDS):
        parsed = reminders.parse(text)
        if not parsed:
            return {"act": "add", "title": "", "due": None}
        due, what = parsed
        hour = time.localtime(due).tm_hour
        # "3'te toplantı" is three in the afternoon, not the night.
        if 1 <= hour <= 7 and not reminders._RELATIVE.search(low) and not any(w in low for w in ("sabah", "gece", "morning")):
            due += 12 * 3600
        title = " ".join(FILLER.sub(" ", what).split()).strip(" '") or ("Toplantı" if "toplant" in low else "Etkinlik")
        return {"act": "add", "title": title[:1].upper() + title[1:], "due": due}
    if not adding and any(word in low for word in LIST_WORDS):
        return {"act": "list", "day": 1 if ("yarın" in low or "yarin" in low or "tomorrow" in low) else 0}
    return None


def _fetch(url: str) -> list[dict]:
    """The link's events, kept for five minutes."""
    import icalendar
    import recurring_ical_events

    with _lock:
        if _cache["url"] == url and time.monotonic() - _cache["at"] < 300:
            return list(_cache["events"])
    req = urllib.request.Request(url.replace("webcal://", "https://", 1), headers={"User-Agent": "Kai"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read(8_000_000)
    calendar = icalendar.Calendar.from_ical(raw)
    today = dt.date.today()
    found = []
    for event in recurring_ical_events.of(calendar).between(today, today + dt.timedelta(days=3)):
        start = event.get("DTSTART").dt
        end = event.get("DTEND").dt if event.get("DTEND") else start
        all_day = not isinstance(start, dt.datetime)
        if all_day:
            start_ts = time.mktime(start.timetuple())
            end_ts = time.mktime(end.timetuple())
        else:
            start_ts = start.timestamp() if start.tzinfo else time.mktime(start.timetuple())
            end_ts = end.timestamp() if isinstance(end, dt.datetime) and end.tzinfo else start_ts
        found.append({
            "title": str(event.get("SUMMARY") or "").strip() or "(adsız)",
            "where": str(event.get("LOCATION") or "").strip(),
            "start": start_ts,
            "end": end_ts,
            "all_day": all_day,
            "uid": f"{event.get('UID')}@{start_ts}",
        })
    found.sort(key=lambda item: item["start"])
    with _lock:
        _cache.update(url=url, at=time.monotonic(), events=found)
    return found


def _day_bounds(offset: int) -> tuple[float, float]:
    day = dt.date.today() + dt.timedelta(days=offset)
    start = time.mktime(day.timetuple())
    return start, start + 86400


def describe_day(settings, offset: int = 0) -> str:
    import reminders

    turkish = getattr(settings, "language", "tr") == "tr"
    url = (getattr(settings, "calendar_ics", "") or "").strip()
    start, end = _day_bounds(offset)
    lines = []
    error = ""
    if url:
        try:
            for item in _fetch(url):
                if item["all_day"]:
                    if item["start"] < end and item["end"] > start:
                        lines.append((start, f"{'tüm gün' if turkish else 'all day'} {item['title']}"))
                elif start <= item["start"] < end:
                    lines.append((item["start"], f"{time.strftime('%H:%M', time.localtime(item['start']))} {item['title']}"))
        except Exception:
            error = "Takvimine ulaşamadım. " if turkish else "I couldn't reach your calendar. "
    for item in reminders.upcoming():
        if start <= item["due"] < end:
            lines.append((item["due"], f"{time.strftime('%H:%M', time.localtime(item['due']))} {'hatırlatma' if turkish else 'reminder'}: {item['text']}".rstrip(": ")))
    lines.sort()
    day = ("bugün" if offset == 0 else "yarın") if turkish else ("today" if offset == 0 else "tomorrow")
    if not lines:
        empty = f"{day.capitalize()} takviminde bir şey yok." if turkish else f"Nothing on your calendar {day}."
        if not url:
            empty += " Takvimini bağlamak için Kai uygulaması › Entegrasyonlar." if turkish else " Link your calendar in the Kai app › Integrations."
        return error + empty
    head = f"{day.capitalize()} {len(lines)} şey var: " if turkish else f"{len(lines)} things {day}: "
    return error + head + "; ".join(text for _at, text in lines) + "."


def _stamp(ts: float) -> str:
    return time.strftime("%Y%m%dT%H%M%S", time.localtime(ts))


def add_event(settings, title: str, due: float | None, minutes: int = 60) -> str:
    """Opens the calendar's new-event page filled in. The user saves it; Kai says so."""
    import reminders

    turkish = getattr(settings, "language", "tr") == "tr"
    if not due:
        return "Ne zaman olsun? Mesela «yarın 3'te toplantı koy» de." if turkish else "When? Say something like «add a meeting tomorrow at 3»."
    url = (getattr(settings, "calendar_ics", "") or "").lower()
    end = due + minutes * 60
    if "outlook" in url or "office365" in url or "live.com" in url:
        query = urllib.parse.urlencode({
            "subject": title,
            "startdt": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(due)),
            "enddt": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(end)),
        }, quote_via=urllib.parse.quote)
        page, where = f"https://outlook.live.com/calendar/0/deeplink/compose?{query}", "Outlook"
    else:
        query = urllib.parse.urlencode({"action": "TEMPLATE", "text": title, "dates": f"{_stamp(due)}/{_stamp(end)}"}, quote_via=urllib.parse.quote)
        page, where = f"https://calendar.google.com/calendar/render?{query}", "Google Takvim" if turkish else "Google Calendar"
    try:
        webbrowser.open(page)
    except Exception:
        return "Takvim sayfasını açamadım." if turkish else "I couldn't open the calendar page."
    told = ""
    if not url and due - LEAD > time.time():
        # Without a calendar link Kai cannot see the event, so it keeps its own reminder.
        reminders.add(due - LEAD, f"{title} 10 dakika sonra" if turkish else f"{title} in 10 minutes")
        told = " 10 dakika önce ben de hatırlatırım." if turkish else " I'll remind you 10 minutes before."
    when = reminders.when(due)
    if turkish:
        return f"«{title}» {when} için {where}'de hazır. Kaydet'e sen bas, ben kaydetmedim.{told}"
    return f"«{title}» at {when} is ready in {where}. Press Save yourself; I didn't save it.{told}"


def start(get_settings, on_due) -> None:
    """Every minute: an event from the calendar link that starts in ten minutes is handed to on_due."""
    told: set[str] = set()

    def loop() -> None:
        while True:
            try:
                settings = get_settings()
                url = (getattr(settings, "calendar_ics", "") or "").strip()
                turkish = getattr(settings, "language", "tr") == "tr"
                if url:
                    now = time.time()
                    for item in _fetch(url):
                        if not item["all_day"] and 0 < item["start"] - now <= LEAD and item["uid"] not in told:
                            told.add(item["uid"])
                            minutes = max(1, round((item["start"] - now) / 60))
                            text = f"{item['title']} {minutes} dakika sonra" if turkish else f"{item['title']} in {minutes} minutes"
                            on_due({"text": text, "kind": "calendar"})
            except Exception:
                pass
            time.sleep(60)

    threading.Thread(target=loop, name="kai-calendar", daemon=True).start()
