"""First start: three short steps so a new Kai can talk. Language, key, city."""

from __future__ import annotations

import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser

import i18n
from i18n import t
from settings import PROVIDERS, Settings
from version import VERSION

# Where each company hands out a key.
KEY_PAGES = {
    "groq": "https://console.groq.com/keys",
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://console.anthropic.com/settings/keys",
    "gemini": "https://aistudio.google.com/apikey",
    "mistral": "https://console.mistral.ai/api-keys",
    "deepseek": "https://platform.deepseek.com/api_keys",
    "xai": "https://console.x.ai",
    "openrouter": "https://openrouter.ai/keys",
}

BG, CARD, FG, MUTED, ACCENT = "#101012", "#1c1c1f", "#f4f4f5", "#a1a1aa", "#35B8FF"
GOOD, BAD = "#4ade80", "#f87171"
WIDTH, HEIGHT = 460, 440


def check_key(provider: str, key: str, timeout: float = 8) -> str:
    """'ok', 'bad' (the company refused it) or 'unknown' (could not ask)."""
    _name, url, _model, wire = PROVIDERS.get(provider, PROVIDERS["groq"])
    if not url or not key:
        return "unknown"
    headers = {"User-Agent": f"Kai/{VERSION}"}
    if wire == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = f"Bearer {key}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url.rstrip("/") + "/models", headers=headers), timeout=timeout):
            return "ok"
    except urllib.error.HTTPError as error:
        return "bad" if error.code in (401, 403) else "unknown"
    except Exception:
        return "unknown"


def needed(settings: Settings) -> bool:
    """A Kai that has never been set up and cannot talk yet."""
    key = settings.groq_key if settings.provider == "groq" else settings.api_key
    return not settings.onboarded and not key


def run_if_new() -> None:
    settings = Settings()
    if needed(settings):
        run(settings)


def run(settings: Settings) -> None:
    """Blocks until the window closes. Whatever was filled in is kept."""
    window = tk.Tk()
    window.title("Kai")
    window.configure(bg=BG)
    window.resizable(False, False)
    window.attributes("-topmost", True)

    step = {"n": 0}
    names = {key: t("set.custom") if key == "custom" else item[0] for key, item in PROVIDERS.items() if key != "custom"}
    language_names = {code: item[0] for code, item in i18n.LANGUAGES.items()}
    language = tk.StringVar(value=language_names.get(settings.language, language_names[i18n.DEFAULT]))
    company = tk.StringVar(value=names.get(settings.provider, "Groq"))
    key_text = tk.StringVar(value="")
    city = tk.StringVar(value=settings.weather_city)
    startup = tk.BooleanVar(value=True)
    verdict = {"text": "", "color": MUTED, "busy": False}

    body = tk.Frame(window, bg=BG)
    body.pack(fill="both", expand=True, padx=26, pady=(22, 0))
    footer = tk.Frame(window, bg=BG)
    footer.pack(side="bottom", fill="x", padx=26, pady=(0, 20))

    def provider_id() -> str:
        return next((key for key, name in names.items() if name == company.get()), "groq")

    def title(text: str) -> None:
        tk.Label(body, text=text, bg=BG, fg=FG, font=("Segoe UI Semibold", 18), anchor="w", justify="left").pack(anchor="w")

    def para(text: str, color: str = MUTED, top: int = 8) -> tk.Label:
        widget = tk.Label(body, text=text, bg=BG, fg=color, font=("Segoe UI", 10), anchor="w", justify="left", wraplength=WIDTH - 52)
        widget.pack(anchor="w", pady=(top, 0))
        return widget

    def dropdown(variable: tk.StringVar, choices) -> None:
        menu = tk.OptionMenu(body, variable, *choices)
        menu.configure(bg=CARD, fg=FG, activebackground=CARD, activeforeground=FG, highlightthickness=0, relief="flat", font=("Segoe UI", 11))
        menu.pack(anchor="w", pady=(6, 0))

    def field(variable: tk.StringVar, secret: bool = False) -> tk.Entry:
        widget = tk.Entry(body, textvariable=variable, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 11), show="•" if secret else "")
        widget.pack(fill="x", pady=(6, 0), ipady=6)
        return widget

    def button(parent, text: str, command, primary: bool = False) -> tk.Button:
        return tk.Button(
            parent, text=text, command=command, relief="flat", padx=16, pady=7, cursor="hand2",
            bg=ACCENT if primary else "#2a2a2e", fg="#041018" if primary else FG,
            font=("Segoe UI Semibold" if primary else "Segoe UI", 10),
        )

    def page_language() -> None:
        title(t("wel.hello"))
        para(t("wel.intro"))
        para(t("set.language"), top=22)
        dropdown(language, language_names.values())

    def page_key() -> None:
        title(t("wel.key_title"))
        para(t("wel.key_why"))
        para(t("set.company"), top=18)
        dropdown(company, names.values())
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(14, 0))
        tk.Label(row, text=t("set.key"), bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
        link = tk.Label(row, text=t("wel.key_get", name=company.get()), bg=BG, fg=ACCENT, font=("Segoe UI", 10, "underline"), cursor="hand2")
        link.pack(side="right")
        link.bind("<Button-1>", lambda _event: webbrowser.open(KEY_PAGES.get(provider_id(), KEY_PAGES["groq"])))
        field(key_text, secret=True).focus_set()
        para(verdict["text"] or t("wel.key_note"), color=verdict["color"] if verdict["text"] else MUTED)

    def page_last() -> None:
        title(t("wel.last_title"))
        para(t("set.city"), top=14)
        field(city)
        tk.Checkbutton(
            body, text=t("wel.startup"), variable=startup, bg=BG, fg=FG, selectcolor=CARD,
            activebackground=BG, activeforeground=FG, font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(14, 0))
        para(t("wel.tips"), top=18)

    pages = [page_language, page_key, page_last]

    def show() -> None:
        for frame in (body, footer):
            for child in frame.winfo_children():
                child.destroy()
        pages[step["n"]]()
        last = step["n"] == len(pages) - 1
        button(footer, t("wel.finish") if last else t("wel.next"), forward, primary=True).pack(side="right")
        if step["n"]:
            button(footer, t("wel.back"), back).pack(side="right", padx=(0, 8))
        for index in range(len(pages)):
            color = ACCENT if index == step["n"] else "#3f3f46"
            tk.Label(footer, text="●", bg=BG, fg=color, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))

    def keep() -> None:
        """Write what is filled in so far."""
        settings.language = next((code for code, name in language_names.items() if name == language.get()), i18n.DEFAULT)
        settings.provider = provider_id()
        typed = key_text.get().strip()
        _name, url, model, _wire = PROVIDERS[settings.provider]
        if settings.provider == "groq":
            settings.groq_key = typed
        else:
            settings.api_key = typed
            settings.api_url = url
            settings.api_model = model
        settings.weather_city = " ".join(city.get().split())[:60] or settings.weather_city
        settings.start_with_windows = bool(startup.get())
        settings.onboarded = True
        settings.save()

    def tested(result: str) -> None:
        verdict["busy"] = False
        if result == "bad":
            # A key the company refuses would leave Kai silent; stay and say so.
            verdict.update(text=t("wel.key_bad"), color=BAD)
            show()
            return
        verdict.update(text=t("wel.key_ok") if result == "ok" else "", color=GOOD)
        step["n"] += 1
        show()

    def forward() -> None:
        if verdict["busy"]:
            return
        if step["n"] == 1 and key_text.get().strip():
            verdict.update(text=t("wel.key_testing"), color=MUTED, busy=True)
            show()
            chosen, typed = provider_id(), key_text.get().strip()
            threading.Thread(target=lambda: results.append(check_key(chosen, typed)), daemon=True).start()
            window.after(150, poll)
            return
        if step["n"] == len(pages) - 1:
            keep()
            window.destroy()
            return
        step["n"] += 1
        show()

    results: list[str] = []

    def poll() -> None:
        if results:
            tested(results.pop())
        else:
            window.after(150, poll)

    def back() -> None:
        if not verdict["busy"]:
            step["n"] -= 1
            show()

    def closed() -> None:
        # Closing is "later": keep what was typed and do not ask again.
        keep()
        window.destroy()

    def language_changed(*_args) -> None:
        i18n.set_language(next((code for code, name in language_names.items() if name == language.get()), i18n.DEFAULT))
        show()

    def company_changed(*_args) -> None:
        verdict.update(text="", color=MUTED)
        if step["n"] == 1:
            show()

    language.trace_add("write", language_changed)
    company.trace_add("write", company_changed)
    window.protocol("WM_DELETE_WINDOW", closed)
    window.bind("<Return>", lambda _event: forward())

    show()
    x = (window.winfo_screenwidth() - WIDTH) // 2
    y = max(0, (window.winfo_screenheight() - HEIGHT) // 2 - 30)
    window.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
    window.mainloop()
