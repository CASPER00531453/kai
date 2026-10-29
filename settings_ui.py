"""Small dark window for Groq, API and voice settings."""

from __future__ import annotations

import threading
import tkinter as tk

import i18n
from i18n import t
from settings import Settings
from voice import voices as voice_list


def open_settings(settings: Settings, on_saved) -> None:
    threading.Thread(target=_run, args=(settings, on_saved), daemon=True).start()


def _run(settings: Settings, on_saved) -> None:
    window = tk.Tk()
    window.title("Kai")
    window.configure(bg="#101012")
    window.resizable(False, False)
    window.attributes("-topmost", True)

    bg = "#101012"
    # The fields scroll; Save and Cancel sit in a footer that is always on
    # screen. The list of fields outgrew small and scaled displays, and the
    # buttons used to end up below the bottom edge.
    footer = tk.Frame(window, bg=bg)
    footer.pack(side="bottom", fill="x")
    canvas = tk.Canvas(window, bg=bg, highlightthickness=0, width=420)
    scroll = tk.Scrollbar(window, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    root = tk.Frame(canvas, bg=bg)
    canvas.create_window((0, 0), window=root, anchor="nw", width=420)
    card = "#1c1c1f"
    fg = "#f4f4f5"
    muted = "#a1a1aa"
    accent = "#35B8FF"

    def label(parent, text):
        return tk.Label(parent, text=text, bg=bg, fg=muted, font=("Segoe UI", 9), anchor="w")

    def entry(parent, text, secret=False):
        widget = tk.Entry(
            parent,
            bg=card,
            fg=fg,
            insertbackground=fg,
            relief="flat",
            font=("Segoe UI", 11),
            show="•" if secret else "",
        )
        widget.insert(0, text)
        return widget

    pad = {"padx": 18}
    tk.Label(root, text=t("set.title"), bg=bg, fg=fg, font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(16, 8), **pad)
    label(root, t("set.language")).pack(anchor="w", **pad)
    language_names = {code: item[0] for code, item in i18n.LANGUAGES.items()}
    language = tk.StringVar(value=language_names.get(settings.language, language_names[i18n.DEFAULT]))
    language_menu = tk.OptionMenu(root, language, *language_names.values())
    language_menu.configure(bg=card, fg=fg, activebackground=card, activeforeground=fg, highlightthickness=0, font=("Segoe UI", 10))
    language_menu.pack(anchor="w", pady=(2, 8), **pad)

    chat_on = tk.BooleanVar(value=settings.chat)
    tk.Checkbutton(
        root,
        text=t("set.chat"),
        variable=chat_on,
        bg=bg,
        fg=fg,
        selectcolor=card,
        activebackground=bg,
        activeforeground=fg,
        font=("Segoe UI", 10),
    ).pack(anchor="w", pady=(0, 8), **pad)
    speak_on = tk.BooleanVar(value=settings.speak)
    tk.Checkbutton(
        root,
        text=t("set.speak"),
        variable=speak_on,
        bg=bg,
        fg=fg,
        selectcolor=card,
        activebackground=bg,
        activeforeground=fg,
        font=("Segoe UI", 10),
    ).pack(anchor="w", pady=(0, 8), **pad)
    mic_on = tk.BooleanVar(value=settings.mic_always)
    tk.Checkbutton(
        root,
        text=t("set.mic"),
        variable=mic_on,
        bg=bg,
        fg=fg,
        selectcolor=card,
        activebackground=bg,
        activeforeground=fg,
        font=("Segoe UI", 10),
    ).pack(anchor="w", pady=(0, 8), **pad)

    from settings import PROVIDERS

    provider = tk.StringVar(value=settings.provider if settings.provider in PROVIDERS else "groq")
    label(root, t("set.company")).pack(anchor="w", **pad)
    names = {key: t("set.custom") if key == "custom" else item[0] for key, item in PROVIDERS.items()}
    picked = tk.StringVar(value=names.get(provider.get(), "Groq"))
    menu = tk.OptionMenu(root, picked, *names.values())
    menu.configure(bg=card, fg=fg, activebackground=card, activeforeground=fg, highlightthickness=0, font=("Segoe UI", 10))
    menu.pack(anchor="w", pady=(2, 8), **pad)

    status = tk.Label(root, text="", bg=bg, fg=muted, font=("Segoe UI", 9), anchor="w")

    label(root, t("set.url")).pack(anchor="w", **pad)
    api_url = entry(root, settings.api_url)
    api_url.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    label(root, t("set.key")).pack(anchor="w", **pad)
    key_box = entry(root, settings.groq_key if provider.get() == "groq" else settings.api_key, secret=True)
    key_box.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    label(root, t("set.model")).pack(anchor="w", **pad)
    model_box = entry(root, settings.groq_model if provider.get() == "groq" else settings.api_model)
    model_box.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    held = {"groq": settings.groq_key, "api": settings.api_key, "groq_model": settings.groq_model, "api_model": settings.api_model}

    def apply_company(*_args) -> None:
        label_now = picked.get()
        chosen = next((key for key, name in names.items() if name == label_now), "groq")
        previous = provider.get()
        if previous == "groq":
            held["groq"] = key_box.get().strip()
            held["groq_model"] = model_box.get().strip()
        else:
            held["api"] = key_box.get().strip()
            held["api_model"] = model_box.get().strip()
        provider.set(chosen)
        _name, url, model, _wire = PROVIDERS[chosen]
        key_box.delete(0, "end")
        model_box.delete(0, "end")
        if chosen == "groq":
            key_box.insert(0, held["groq"])
            model_box.insert(0, held["groq_model"] or model)
            api_url.delete(0, "end")
            api_url.insert(0, url)
        else:
            key_box.insert(0, held["api"])
            model_box.insert(0, model if chosen != "custom" else (held["api_model"] or settings.api_model))
            if chosen != "custom":
                api_url.delete(0, "end")
                api_url.insert(0, url)
        status.configure(text=t("set.picked", name=label_now))

    picked.trace_add("write", apply_company)

    label(root, t("set.size")).pack(anchor="w", **pad)
    island_scale = entry(root, str(settings.island_scale))
    island_scale.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    label(root, t("set.city")).pack(anchor="w", **pad)
    weather_city = entry(root, settings.weather_city)
    weather_city.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    label(root, "GitHub token").pack(anchor="w", **pad)
    github_token = entry(root, settings.github_token, secret=True)
    github_token.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    label(root, "Vercel token").pack(anchor="w", **pad)
    vercel_token = entry(root, settings.vercel_token, secret=True)
    vercel_token.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    label(root, t("set.stripe")).pack(anchor="w", **pad)
    stripe_key = entry(root, settings.stripe_key, secret=True)
    stripe_key.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    label(root, t("set.eleven_key")).pack(anchor="w", **pad)
    eleven_key = entry(root, settings.elevenlabs_key, secret=True)
    eleven_key.pack(fill="x", pady=(2, 8), ipady=4, **pad)

    label(root, t("set.eleven_voice")).pack(anchor="w", **pad)
    voice_row = tk.Frame(root, bg=bg)
    voice_row.pack(fill="x", pady=(2, 8), **pad)
    eleven_voice = entry(voice_row, settings.elevenlabs_voice)
    eleven_voice.pack(side="left", fill="x", expand=True, ipady=4)

    def fill_voices() -> None:
        voices = voice_list()
        menu = tk.Menu(root, tearoff=0, bg=card, fg=fg)
        for name, voice_id in voices:
            menu.add_command(
                label=name,
                command=lambda vid=voice_id: (eleven_voice.delete(0, "end"), eleven_voice.insert(0, vid)),
            )
        menu.tk_popup(voice_row.winfo_rootx(), voice_row.winfo_rooty() + voice_row.winfo_height())
        status.configure(text=t("set.voice_count", n=len(voices)))

    tk.Button(voice_row, text=t("set.voices"), command=fill_voices, bg="#2a2a2e", fg=fg, relief="flat", font=("Segoe UI", 9), padx=10).pack(side="left", padx=(8, 0))

    status.pack(anchor="w", pady=(0, 6), **pad)

    def save() -> None:
        settings.language = next((code for code, name in language_names.items() if name == language.get()), i18n.DEFAULT)
        settings.chat = bool(chat_on.get())
        settings.mic_always = bool(mic_on.get())
        settings.speak = bool(speak_on.get())
        settings.provider = provider.get() if provider.get() in PROVIDERS else "groq"
        settings.api_url = api_url.get().strip() or PROVIDERS.get(settings.provider, PROVIDERS["openai"])[1] or "https://api.openai.com/v1"
        typed_key = key_box.get().strip()
        typed_model = model_box.get().strip()
        if settings.provider == "groq":
            settings.groq_key = typed_key
            settings.groq_model = typed_model or "qwen/qwen3.8-27b"
        else:
            settings.api_key = typed_key
            settings.api_model = typed_model or PROVIDERS[settings.provider][2] or "gpt-4o-mini"
        try:
            settings.island_scale = max(40, min(160, int(island_scale.get().strip() or "50")))
        except ValueError:
            settings.island_scale = 50
        settings.weather_city = " ".join(weather_city.get().split())[:60]
        settings.github_token = github_token.get().strip()
        settings.vercel_token = vercel_token.get().strip()
        settings.stripe_key = stripe_key.get().strip()
        settings.elevenlabs_key = eleven_key.get().strip()
        settings.elevenlabs_voice = eleven_voice.get().strip() or "nPczCjzI2devNBz1zQrb"
        settings.save()
        on_saved()
        window.destroy()

    buttons = tk.Frame(footer, bg=bg)
    buttons.pack(anchor="e", pady=(10, 14), **pad)
    tk.Button(buttons, text=t("set.cancel"), command=window.destroy, bg="#2a2a2e", fg=fg, relief="flat", font=("Segoe UI", 10), padx=14, pady=6).pack(side="right")
    tk.Button(buttons, text=t("set.save"), command=save, bg=accent, fg="#041018", relief="flat", font=("Segoe UI Semibold", 10), padx=14, pady=6).pack(side="right", padx=(0, 8))

    window.update_idletasks()
    sx = window.winfo_screenwidth()
    sy = window.winfo_screenheight()
    body = root.winfo_reqheight()
    foot = footer.winfo_reqheight()
    # Never taller than the screen, with room for the taskbar and title bar.
    height = min(body + foot, sy - 120)
    canvas.configure(scrollregion=(0, 0, 420, body), height=height - foot)
    width = 420
    if body + foot > height:
        scroll.pack(side="right", fill="y")
        width += scroll.winfo_reqwidth()
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(-event.delta // 120, "units"))
    window.geometry(f"{width}x{height}+{(sx - width) // 2}+{max(0, (sy - height) // 2 - 20)}")
    window.mainloop()
