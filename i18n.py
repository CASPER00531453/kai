"""Kai's language. Menus and fixed lines are written in Turkish and English.

Every other language still gets heard, answered and spoken in that language;
only the menus and the fixed lines fall back to English.
"""

from __future__ import annotations

DEFAULT = "tr"

# code -> (own name, English name, speech locale, how Kai addresses the user)
LANGUAGES = {
    "tr": ("Türkçe", "Turkish", "tr-TR", "patron"),
    "en": ("English", "English", "en-US", "boss"),
    "de": ("Deutsch", "German", "de-DE", "Chef"),
    "fr": ("Français", "French", "fr-FR", "patron"),
    "es": ("Español", "Spanish", "es-ES", "jefe"),
    "it": ("Italiano", "Italian", "it-IT", "capo"),
    "pt": ("Português", "Portuguese", "pt-BR", "chefe"),
    "ru": ("Русский", "Russian", "ru-RU", "босс"),
    "ar": ("العربية", "Arabic", "ar-SA", "يا ريس"),
    "az": ("Azərbaycanca", "Azerbaijani", "az-AZ", "patron"),
}

_lang = DEFAULT
# Only Kai's owner is "patron" (admin.py); everyone else is spoken to plainly.
_admin = False


def set_language(code: str) -> None:
    global _lang
    _lang = code if code in LANGUAGES else DEFAULT


def set_admin(on: bool) -> None:
    global _admin
    _admin = bool(on)


def is_admin() -> bool:
    return _admin


_ADDRESS = None


def address(text: str) -> str:
    """The fixed lines say "patron" / "boss"; for anyone but the owner the word goes.

    "Tamam patron, açtım." -> "Tamam, açtım."  "Patron, bulamadım." -> "Bulamadım."
    """
    global _ADDRESS
    if _admin or not text:
        return text
    import re

    if _ADDRESS is None:
        word = r"(?:patron|boss)"
        _ADDRESS = (
            (re.compile(r"^The boss\b"), lambda m: "The user"),
            (re.compile(r"^Patron (?=[^,])"), lambda m: "Kullanıcı "),
            (re.compile(rf"^{word},\s*(\S)", re.IGNORECASE), lambda m: "İ" if m.group(1) == "i" else m.group(1).upper()),
            (re.compile(rf",?\s+{word}(?=[.,!?:;)]|$)", re.IGNORECASE), lambda m: ""),
        )
    for pattern, repl in _ADDRESS:
        text = pattern.sub(repl, text)
    return text


def current() -> str:
    return _lang


def locale() -> str:
    return LANGUAGES[_lang][2]


def reply_rule() -> str:
    """Appended to the Turkish prompts so the model answers in the chosen language."""
    if _lang == "tr":
        return ""
    _own, english, _locale, boss = LANGUAGES[_lang]
    return f" IMPORTANT: Whatever language these instructions are written in, always reply in {english}." + (
        f" Where you would address the user as 'patron', say '{boss}'." if _admin else ""
    )


def t(key: str, **values) -> str:
    tr, en = STRINGS[key]
    text = tr if _lang == "tr" else en
    return address(text.format(**values) if values else text)


# key -> (Türkçe, English)
STRINGS = {
    # tray
    "tray.dynamic": ("Dinamik ada modu", "Dynamic island mode"),
    "tray.screen": ("Ekranı izle", "Watch the screen"),
    "tray.dot": ("Mavi nokta", "Blue dot"),
    "tray.chat": ("Yazılı sohbet", "Written chat"),
    "tray.mic": ("Sürekli dinle", "Always listen"),
    "tray.size": ("Ada boyutu", "Island size"),
    "tray.voice": ("Kai sesi", "Kai's voice"),
    "tray.quality": ("ElevenLabs kalitesi", "ElevenLabs quality"),
    "tray.startup": ("Windows açılınca başlat", "Start with Windows"),
    "tray.settings": ("Ayarlar", "Settings"),
    "tray.hooks": ("Claude kancası kur", "Install Claude hook"),
    "tray.pause": ("Duraklat", "Pause"),
    "tray.music": ("Müzik demosu", "Music demo"),
    "tray.quit": ("Çıkış", "Quit"),
    "quality.v3": ("En doğal (v3)", "Most natural (v3)"),
    "quality.v2": ("Dengeli (multilingual v2)", "Balanced (multilingual v2)"),
    "quality.flash": ("En hızlı (flash)", "Fastest (flash)"),
    # settings window
    "wel.hello": ("Selam, ben Kai", "Hi, I'm Kai"),
    "wel.intro": (
        "Ekranının üstünde duran kişisel asistanınım. Üç kısa adımda hazır olurum.",
        "Your personal assistant, living at the top of your screen. Three short steps and I'm ready.",
    ),
    "wel.key_title": ("Kai'ye bir beyin lazım", "Kai needs a brain"),
    "wel.key_why": (
        "Düşünebilmem için bir yapay zekâ anahtarı gerekiyor. Groq ücretsiz veriyor: siteye gir, hesap aç, "
        "\"Create API Key\" de, çıkan anahtarı kopyalayıp buraya yapıştır.",
        "I need an AI key to think. Groq gives one for free: open the site, sign up, press "
        "\"Create API Key\", then copy the key and paste it here.",
    ),
    "wel.key_get": ("{name} anahtarı al ↗", "Get a {name} key ↗"),
    "wel.key_note": (
        "Anahtar sadece bu bilgisayarda saklanır. Boş bırakıp sonra ayarlardan da girebilirsin.",
        "The key stays on this computer. You can leave it empty and add it later in settings.",
    ),
    "wel.key_testing": ("Anahtar deneniyor…", "Checking the key…"),
    "wel.key_ok": ("Anahtar çalışıyor.", "The key works."),
    "wel.key_bad": (
        "Bu anahtar kabul edilmedi. Baştan sona kopyaladığına bak ya da kutuyu boşaltıp devam et.",
        "This key was refused. Check you copied all of it, or clear the box and continue.",
    ),
    "wel.last_title": ("Son dokunuşlar", "Finishing touches"),
    "wel.startup": ("Windows açılınca Kai de başlasın", "Start Kai when Windows starts"),
    "wel.tips": (
        "Nasıl kullanılır: fareyi ekranın üst ortasına götür, ada açılır ve yazarsın. "
        "Konuşmak için sağ Alt (AltGr) tuşunu basılı tut. Ayarların hepsi adadaki çarkta.",
        "How it works: move the mouse to the top centre of the screen, the island opens and you type. "
        "Hold the right Alt (AltGr) key to talk. Every setting is behind the gear on the island.",
    ),
    "wel.next": ("Devam", "Next"),
    "wel.back": ("Geri", "Back"),
    "wel.finish": ("Başla", "Start"),
    "set.title": ("Kai ayarları", "Kai settings"),
    "set.language": ("Dil", "Language"),
    "set.chat": ("Yazılı sohbet, adanın altında", "Written chat, under the island"),
    "set.speak": ("Sesli konuş (kapalıyken sadece yazar)", "Speak out loud (off means text only)"),
    "set.mic": ("Sürekli dinle, ayardan kapanana kadar", "Always listen, until turned off here"),
    "set.company": ("Firma", "Provider"),
    "set.custom": ("Özel adres", "Custom address"),
    "set.url": ("API adresi", "API address"),
    "set.key": ("Anahtar", "Key"),
    "set.model": ("Model", "Model"),
    "set.size": ("Ada boyutu % (50 küçük, 100 büyük)", "Island size % (50 small, 100 large)"),
    "set.city": ("Hava durumu şehri", "Weather city"),
    "set.stripe": ("Stripe gizli anahtar", "Stripe secret key"),
    "set.eleven_key": ("ElevenLabs anahtarı", "ElevenLabs key"),
    "set.eleven_voice": ("ElevenLabs sesi", "ElevenLabs voice"),
    "set.voices": ("Sesler", "Voices"),
    "set.voice_count": ("{n} ses", "{n} voices"),
    "set.picked": ("{name} seçili", "{name} selected"),
    "set.cancel": ("İptal", "Cancel"),
    "set.save": ("Kaydet", "Save"),
    # island
    "listening": ("dinliyor", "listening"),
    "looking": ("bakıyorum", "on it"),
    "ready": ("hazır", "ready"),
    "ok": ("tamam", "ok"),
    "drop": ("bırak", "drop"),
    "chat": ("sohbet", "chat"),
    "code": ("kod", "code"),
    "you": ("Sen", "You"),
    "send": ("Gönder", "Send"),
    "no_mic": ("mikrofon yok", "no microphone"),
    "mic_failed": ("Mikrofon açılmadı", "The microphone did not open"),
    "mic_failed_boss": ("Mikrofon açılmadı patron.", "The microphone did not open, boss."),
    "now_playing": ("Şimdi çalıyor", "Now playing"),
    "nothing_playing": ("Bir şey çalmıyor", "Nothing is playing"),
    "camera_failed": ("Kamera açılmadı", "The camera did not open"),
    # fixed lines Kai says
    "not_heard": ("Duyamadım patron, bir daha söyler misin?", "I didn't catch that, boss. Say it again?"),
    "too_slow": ("Biraz uzun sürdü patron, bir daha deneriz.", "That took too long, boss. Let's try again."),
    "empty": ("cevap boş", "empty answer"),
    "no_link": ("bağlantı yok", "no connection"),
    "cant_answer": ("Şu an cevap veremedim.", "I couldn't answer just now."),
    "cant_pick": ("seçemedim", "couldn't pick it"),
    "saw_nothing": ("Bir şey seçemedim patron.", "I couldn't make anything out, boss."),
    "done": ("isteğiniz tamamlandı", "your request is done"),
    "done_spoken": ("İsteğiniz tamamlandı patron", "Your request is done, boss"),
    "permit_ask": (
        "İzin istiyor patron. Allow ya da not allow. Onaylıyorum da diyebilirsin.",
        "It is asking for permission, boss. Say allow or not allow.",
    ),
    "permit_yes": ("Onayladım patron.", "Allowed, boss."),
    "permit_no": ("Reddettim patron.", "Denied, boss."),
    "watch_screen": ("Tamam patron, ekranı izliyorum.", "Okay boss, I'm watching the screen."),
    "watch_camera": ("Tamam patron, kamerayı izliyorum.", "Okay boss, I'm watching the camera."),
    "watch_stop": ("Tamam patron, izlemeyi bıraktım.", "Okay boss, I stopped watching."),
    "need_eleven": (
        "Önce Ayarlar'a ElevenLabs anahtarını yapıştır patron.",
        "Paste your ElevenLabs key into Settings first, boss.",
    ),
    "eleven_hint": (
        "ElevenLabs anahtarını sağ tık, Ayarlar kısmına yapıştır.",
        "Right click, then paste your ElevenLabs key into Settings.",
    ),
    "preview": ("Merhaba patron, ben Kai. Bu sesim nasıl?", "Hello boss, I'm Kai. How does this voice sound?"),
    "already_open": ("Kai zaten açık. Sağ alttaki oka bas, orada.", "Kai is already running. Click the arrow at the bottom right, it is there."),
    "playing_game": ("Patron şu an {game} oynuyor. {heard}", "The boss is playing {game} right now. {heard}"),
    "game": ("Oyun: {game}. {heard}", "Game: {game}. {heard}"),
    "file.unreadable": (
        "Patron, {name} dosyasını okuyamadım. Metin, kod, PDF, Word ya da resim olmalı.",
        "Boss, I couldn't read {name}. It has to be text, code, a PDF, a Word file or an image.",
    ),
    # favourites and League
    "fav_none_playing": ("Patron, şu an kaydedecek bir şarkı yok.", "Boss, there is no song to save right now."),
    "fav_saved": ("Favorin bu oldu patron: {song}", "This is your favourite now, boss: {song}"),
    "fav_missing": (
        "Patron, favori şarkın yok. Çalarken favorim de.",
        "Boss, you have no favourite song. Say favourite while one is playing.",
    ),
    "lol_on": ("Tamam patron, karşılaşma bulununca kabul edeceğim.", "Okay boss, I'll accept the match when it is found."),
    "lol_off": ("Kabulü bıraktım patron.", "I stopped accepting, boss."),
    "lol_ask": (
        "Lock inlemek istediğin karakter var mı? İsmini yaz, yoksa yok de.",
        "Any champion you want to lock in? Type the name, or say no.",
    ),
    "lol_skip": ("Tamam patron, karakter seçmiyorum.", "Okay boss, I won't pick a champion."),
    "lol_unknown": ("Patron, {name} diye bir şampiyon bulamadım.", "Boss, I couldn't find a champion called {name}."),
    "lol_closed": ("Patron, şampiyon seçme ekranı açık değil.", "Boss, champion select is not open."),
    "lol_locked": ("{name} kilitlendi patron.", "{name} is locked in, boss."),
    # apps and Spotify
    "app.searched": ("Spotify'da {query} aradım patron, listeden birine bas.", "I searched Spotify for {query}, boss. Pick one from the list."),
    "app.playing": ("{name} açıldı patron.", "{name} is playing, boss."),
    "app.no_media": ("Patron, çalan bir şey bulamadım.", "Boss, I couldn't find anything playing."),
    "app.pause": ("Durdurdum patron.", "Paused, boss."),
    "app.resume": ("Devam ediyor patron.", "Playing again, boss."),
    "app.next": ("Sonraki parçaya geçtim patron.", "Skipped to the next track, boss."),
    "app.prev": ("Öncekine aldım patron.", "Back to the previous one, boss."),
    "app.toggle": ("Tamam patron.", "Okay boss."),
    "app.refuse": ("Patron, bunu açmam.", "Boss, I won't open that."),
    "app.not_found": ("Patron, {label} diye bir şey bulamadım bu bilgisayarda.", "Boss, I couldn't find {label} on this computer."),
    "app.steam_first": ("Önce Steam'i açıyorum patron, ardından {label} geliyor.", "Opening Steam first, boss, then {label}."),
    "app.opening": ("Emredersin patron, {label} açılıyor.", "Right away boss, opening {label}."),
    "app.cant_close": ("Patron, {label} kapatmayı henüz bilmiyorum.", "Boss, I don't know how to close {label} yet."),
    "app.closed": ("{label} kapattım patron.", "I closed {label}, boss."),
    "app.open_failed": ("Patron, {label} açılmadı, kurulu mu bir bak.", "Boss, {label} didn't open. Check that it is installed."),
    "app.close_failed": ("Patron, {label} kapanmadı.", "Boss, {label} didn't close."),
    "click.none": (
        "Patron, ekranda basacak bir şey seçemedim. Oyunun veya uygulamanın üstüne gelip bir daha söyle.",
        "Boss, I couldn't find anything to press on screen. Hover the game or app and say it again.",
    ),
    "click.played": ("Bastım patron.", "Pressed it, boss."),
    "click.opened": ("Açtım patron.", "Opened it, boss."),
    # typing into other apps
    "type.empty": ("Patron, ne yazayım onu söylemedin.", "Boss, you didn't say what to type."),
    "type.here": ("açık pencere", "the open window"),
    "type.closed": ("Patron, {label} açık değil, önce aç sonra yazayım.", "Boss, {label} is not open. Open it first, then I'll type."),
    "type.no_window": ("Patron, yazacak pencere bulamadım.", "Boss, I couldn't find a window to type into."),
    "type.unsafe": ("Patron, oraya güvenlik için yazmıyorum.", "Boss, I don't type there, for safety."),
    "type.no_focus": (
        "Patron, {label} penceresini öne getiremedim, bir kere tıkla sonra tekrar söyle.",
        "Boss, I couldn't bring {label} to the front. Click it once and say it again.",
    ),
    "type.lost_focus": ("Patron, {label} odaktan çıktı, yazmadım.", "Boss, {label} lost focus, so I didn't type."),
    "type.sent": ("{label} için yazıp gönderdim patron.", "Typed and sent it in {label}, boss."),
    "type.typed": (
        "{label} için yazdım patron, göndermek için Enter'a bas ya da 'gönder' de.",
        "Typed it in {label}, boss. Press Enter to send.",
    ),
    # Claude hook
    "agents.unreadable": ("{path} okunamadı, dokunmadım.", "Could not read {path}, so I left it alone."),
    "agents.bad_json": ("{path} bozuk JSON, dokunmadım.", "{path} is not valid JSON, so I left it alone."),
    "agents.unexpected": ("{what} beklenmedik türde, dokunmadım.", "{what} has an unexpected type, so I left it alone."),
    "agents.foreign": ("{what} Kai'nin yazdığı bir şey değil, dokunmadım.", "{what} was not written by Kai, so I left it alone."),
    "agents.unknown": ("\"{id}\" diye bir ajan tanımıyorum.", "Unknown agent \"{id}\"."),
    "agents.failed": ("Yazamadım: {why}", "Could not write: {why}"),
    "agents.removed": ("{name} bağlantısı kaldırıldı.", "{name} disconnected."),
    "agents.note.codex": ("Codex bağlandı. Yeni kancaları bir kere onaylaman lazım: Codex'i aç, /hooks yaz.", "Codex connected. It runs new hooks only once you trust them: start Codex and review them with /hooks."),
    "agents.note.copilot": ("Copilot CLI bağlandı. Yeni bir oturum aç.", "Copilot CLI connected. Start a new session."),
    "agents.note.gemini": ("Gemini CLI bağlandı. Yeni bir oturum aç.", "Gemini CLI connected. Start a new session."),
    "agents.note.antigravity": ("Antigravity bağlandı. Yeni bir sohbet aç.", "Antigravity connected. Start a new conversation."),
    "agents.note.cursor": ("Cursor bağlandı. Cursor'ı yeniden başlat.", "Cursor connected. Restart Cursor."),
    "agents.note.muse": ("Muse Code bağlandı. Yeni bir oturum aç.", "Muse Code connected. Start a new session."),
    "agents.note.opencode": ("OpenCode bağlandı. OpenCode'u yeniden başlat.", "OpenCode connected. Restart OpenCode."),
    "agents.note.amp": ("Amp bağlandı. Amp'i yeniden başlat.", "Amp connected. Restart Amp."),
    "agents.note.hermes": ("Hermes bağlandı. Bir kere `hermes plugins enable kai` çalıştır, sonra yeni oturum aç.", "Hermes connected. Run `hermes plugins enable kai` once, then start a new session."),
    "claude.tool": ("bir araç", "a tool"),
    "claude.wants": ("{tool} için izin istiyor", "wants permission for {tool}"),
    "claude.failed": ("Claude {tool} hata verdi", "Claude {tool} failed"),
    "claude.tool_short": ("araç", "tool"),
    "claude.finished": ("Claude işi bitirdi", "Claude finished"),
    "claude.prompted": ("Claude'a yazdın", "You wrote to Claude"),
    "claude.asks": ("İzin istiyor", "Asking for permission"),
    "claude.not_object": ("Claude ayarı bir nesne değil, dokunmadım.", "Claude's settings are not an object, so I left them alone."),
    "claude.bad_json": ("Claude ayarı bozuk JSON, dokunmadım.", "Claude's settings are broken JSON, so I left them alone."),
    "claude.installed": (
        "Claude kancası kuruldu. Yeni oturumda Kai haberi görür.",
        "Claude hook installed. Kai sees events from the next session.",
    ),
    "stripe.linked": ("Stripe bağlı", "Stripe connected"),
    # weather
    "sky.clear": ("Açık", "Clear"),
    "sky.partly": ("Parçalı bulutlu", "Partly cloudy"),
    "sky.cloudy": ("Bulutlu", "Cloudy"),
    "sky.fog": ("Sisli", "Foggy"),
    "sky.rain": ("Yağmurlu", "Rainy"),
    "sky.snow": ("Karlı", "Snowy"),
    "sky.storm": ("Fırtınalı", "Stormy"),
    "sky.no_city": ("{city} diye bir şehir bulamadım", "Couldn't find a city called {city}"),
    # memory
    "mem.saved": ("Tamam patron, aklımda: {fact}", "Got it, boss, I'll remember: {fact}"),
    "mem.what": ("Neyi hatırlayayım patron?", "What should I remember, boss?"),
    "mem.empty": ("Patron, henüz hatırladığım bir şey yok. 'Şunu hatırla' diye başla.", "Boss, I don't remember anything yet. Start with 'remember that'."),
    "mem.list": ("Hatırladıklarım patron: {facts}", "What I remember, boss: {facts}"),
    "mem.forgot": ("Unuttum patron ({count} şey).", "Forgotten, boss ({count})."),
    "mem.forgot_none": ("Patron, öyle bir şey hatırlamıyordum zaten.", "Boss, I didn't remember anything like that."),
    "mem.cleared": ("Hafızamı sildim patron, her şeyi unuttum.", "Memory wiped, boss. I forgot everything."),
    # reminders
    "rem.set": ("Tamam patron, {when} hatırlatacağım: {text}", "Okay boss, I'll remind you {when}: {text}"),
    "rem.set_plain": ("Tamam patron, {when} haber vereceğim.", "Okay boss, I'll let you know {when}."),
    "rem.when": ("Ne zaman hatırlatayım patron? Mesela '20 dakika sonra' ya da 'yarın 9'da'.", "When should I remind you, boss? Say '20 minutes' or 'tomorrow at 9'."),
    "rem.in_minutes": ("{minutes} dakika sonra ({clock})", "in {minutes} minutes ({clock})"),
    "rem.tomorrow": ("yarın {clock}", "tomorrow at {clock}"),
    "rem.fire": ("Patron, hatırlatma: {text}", "Boss, reminder: {text}"),
    "rem.fire_plain": ("Patron, zaman doldu.", "Boss, time's up."),
    "rem.none": ("Patron, kurulu bir hatırlatma yok.", "Boss, there are no reminders."),
    "rem.list": ("Hatırlatmaların patron: {items}", "Your reminders, boss: {items}"),
    "rem.cleared": ("{count} hatırlatmayı sildim patron.", "Deleted {count} reminders, boss."),
    # computer control
    "sys.vol_up": ("Sesi açtım patron.", "Turned the volume up, boss."),
    "sys.vol_down": ("Sesi kıstım patron.", "Turned the volume down, boss."),
    "sys.vol_mute": ("Sesi kapattım patron.", "Muted, boss."),
    "sys.brightness": ("Parlaklık %{level} patron.", "Brightness {level}%, boss."),
    "sys.no_brightness": ("Patron, bu ekranın parlaklığını değiştiremiyorum.", "Boss, I can't change this screen's brightness."),
    "sys.locked": ("Kilitledim patron.", "Locked it, boss."),
    "sys.sleeping": ("Uyutuyorum patron.", "Putting it to sleep, boss."),
    "sys.shutdown_now": ("Kapatıyorum patron.", "Shutting down, boss."),
    "sys.shutdown_in": ("{minutes} dakika sonra kapatacağım patron. Vazgeçersen 'kapatmayı iptal et' de.", "I'll shut down in {minutes} minutes, boss. Say 'cancel shutdown' to stop it."),
    "sys.restart_now": ("Yeniden başlatıyorum patron.", "Restarting, boss."),
    "sys.restart_in": ("{minutes} dakika sonra yeniden başlatacağım patron.", "I'll restart in {minutes} minutes, boss."),
    "sys.power_cancelled": ("İptal ettim patron, kapanmıyor.", "Cancelled it, boss, no shutdown."),
    "sys.nothing_scheduled": ("Patron, zaten planlanmış bir kapatma yok.", "Boss, there is no shutdown scheduled."),
    "sys.failed": ("Patron, bunu yapamadım.", "Boss, I couldn't do that."),
    # updates
    "upd.version": ("Kai {v}", "Kai {v}"),
    "upd.check": ("Güncellemeleri denetle", "Check for updates"),
    "upd.install": ("Güncelle → {v}", "Update → {v}"),
    "upd.available": ("Kai {v} çıktı patron. Tepsiden ya da adanın ayarlarından güncelleyebilirsin.", "Kai {v} is out, boss. Update from the tray or the island settings."),
    "upd.latest": ("Kai güncel patron ({v}).", "Kai is up to date, boss ({v})."),
    "upd.downloading": ("Güncelleme iniyor patron, bitince Kai kendini yeniden açacak.", "Downloading the update, boss. Kai will restart itself."),
    "upd.failed": ("Güncelleme olmadı patron ({err}).", "The update failed, boss ({err})."),
    "upd.norepo": ("Bu Kai için güncelleme adresi ayarlanmamış.", "No update source is set for this Kai."),
    "claude.no_python": ("Claude kancası için Python lazım; bu bilgisayarda bulamadım.", "The Claude hook needs Python, and I couldn't find it on this computer."),
    # errors
    "err.groq_blocked": ("Groq isteği engellendi", "The Groq request was blocked"),
    "err.bad_key": ("API anahtarı geçersiz", "The API key is not valid"),
    "err.no_model": ("model bulunamadı", "model not found"),
    "err.rate": ("Groq sınırı doldu (rate limit), bir dakika bekle patron.", "Groq rate limit reached. Wait a minute, boss."),
    "err.key_missing": ("{who} anahtarı yok", "No {who} key"),
    "err.key_broken": (
        "{who} anahtarı bozuk. Ayarlardan tekrar yapıştır, içine Türkçe karakter karışmış.",
        "The {who} key is broken. Paste it again in Settings, a non-English character got into it.",
    ),
    "err.edge": ("Microsoft'un ücretsiz sesi şu an çalışmıyor. Kai uygulaması › Sohbet › Ses'ten internetsiz Türkçe sesi indir.", "Microsoft's free voice is not working right now. Pick another voice or add an ElevenLabs key."),
    "err.eleven_paid": (
        "Bu ElevenLabs sesi ücretli plan istiyor, sağ tık Kai sesi menüsünden başka ses seç",
        "This ElevenLabs voice needs a paid plan. Right click and pick another one under Kai's voice",
    ),
    "err.eleven_perm": ("ElevenLabs anahtarında Text to Speech izni kapalı", "The ElevenLabs key has Text to Speech turned off"),
    "err.eleven_quota": ("ElevenLabs kotası doldu", "ElevenLabs quota is used up"),
    "err.eleven_key": ("ElevenLabs anahtarı geçersiz", "The ElevenLabs key is not valid"),
    "err.eleven_link": ("ElevenLabs'e bağlanamadı", "Couldn't reach ElevenLabs"),
}
