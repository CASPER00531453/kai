// Kai pages: General, Mascot, Agents, Chat, OK Kai, Integrations, Shortcuts.

import { BotEngine } from "../mochi/engine";
import { PICKABLE, mascotLabel, type Mascot } from "../mochi/mascots";
import { BODY_COLORS, hueColor, setBodyColor } from "../mochi/palette";
import { h } from "../views/dom";
import { keyLabel } from "./keys";
import { Api } from "./api";
import type { Ctx } from "./flowpages";
import { enginePicker, modelsGrid } from "./flowpages";
import { showTour } from "./tour";
import { button, card, input, keycap, L, pill, row, segmented, select, toast, toggle } from "./ui";

// ── General ─────────────────────────────────────────────────────────────────

export function generalPage(ctx: Ctx): HTMLElement {
  const i = ctx.state.island;
  const set = async (k: string, v: unknown) => { await Api.set(k, v); await ctx.refresh(); };
  const upd = ctx.state.update;
  const f = ctx.state.flow;
  const updBtn = upd.available
    ? button(L(`Güncelle → ${upd.latest}`, `Update → ${upd.latest}`), async () => { await Api.update("install"); toast(L("Güncelleme indiriliyor…", "Downloading the update…")); }, "primary")
    : button(L("Güncellemeleri denetle", "Check for updates"), async () => { await Api.update("check"); await ctx.refresh(); toast(ctx.state.update.available ? L("Yeni sürüm var", "An update is available") : L("Kai güncel", "Kai is up to date")); }, "ghost");
  const volume = h("input", { type: "range", class: "a-range", min: "0", max: "0.2", step: "0.01" }) as HTMLInputElement;
  volume.value = String(i.sfx_volume);
  volume.addEventListener("change", () => void set("sfx_volume", Number(volume.value)));
  return h(
    "div",
    { class: "a-page" },
    card(
      null,
      row(L("Dil", "Language"), null, select(i.languages.map(([code, name]) => [name, code]), i.language, (v) => void set("language", v))),
      row(L("Windows açılınca başlat", "Start with Windows"), null, toggle(i.startup, (on) => void set("startup", on))),
      row(L("Kai'ı açınca bu pencere de açılsın", "Open this window when you start Kai"), L("Windows ile başlarken açılmaz.", "Not when Kai starts with Windows."), toggle(ctx.state.flow.app_on_launch, (on) => void set("app_on_launch", on))),
      row(L("Ses efektleri", "Sound effects"), null, h("div", { class: "a-inline" }, volume, toggle(i.sfx, (on) => void set("sfx", on)))),
    ),
    card(
      L("Ada", "Island"),
      row(L("Adada saat", "Clock in the island"), L("Ada küçükken ortasında tarih ve saat.", "The date and time in the middle of the island when it is compact."), toggle(f.show_clock, (on) => void set("show_clock", on))),
      row(L("Küçük adada plan kullanımı", "Plan usage in the compact island"), L("Claude planının yüzde kaçı gitti, ada küçükken de görünür. Tıklayınca ayrıntısı açılır.", "How much of the Claude plan is used, even when the island is compact. Click it for the details."), toggle(f.plan_in_compact, (on) => void set("plan_in_compact", on))),
      row(L("Tüm hapların uyarıları", "Alerts from every pill"), L("Başka bir hap bitince ya da hata verince ada bir anlığına açılır, sonra senin hapın geri gelir.", "Another pill that finishes or fails opens the island for a moment, then your pill comes back."), toggle(f.alerts_all_pills, (on) => void set("alerts_all_pills", on))),
      row(L("Kai bilgisayarı hisseder", "Kai feels your PC"), L("İşlemci tavan yapınca panik, ısınınca kızarma, bellek dolunca şişme, pil bitince uyuklama. Kai'nin üstüne gelince nedenini yazar.", "Panics under full processor load, flushes when warm, puffs up when memory is short, dozes on a low battery. Point at Kai to see why."), toggle(f.feels_pc, (on) => void set("feels_pc", on))),
      row(L("Günün özeti", "Daily summary"), L("Her akşam bu saatte Kai gözlüğünü takar, günün raporunu okur: Claude ile ne yaptın, kaç dosya değişti, yarın neler var.", "Every evening at this time Kai puts its glasses on and reads you the day's report: what you did with Claude, how many files changed, what's on tomorrow."),
        h("div", { class: "a-inline" },
          input(f.summary_time || "21:00", "21:00", (v) => void set("summary_time", v), { type: "time" }),
          toggle(f.summary_enabled, (on) => void set("summary_enabled", on)))),
    ),
    card(L("Sürüm", "Version"), row(`Kai ${upd.current || i.version}`, upd.error ? upd.error : null, updBtn),
      row("Casper Technology", L("Kai'yi yapan ekip. Tüm hakları saklıdır.", "The team that makes Kai. All rights reserved."), h("div", { class: "a-inline" },
        button(L("Lisansı aç", "View license"), () => void Api.openLicense(), "ghost"),
        button(L("Siteye git", "Visit website"), () => void Api.openUrl("https://casper-technology.vercel.app/"), "ghost"))),
      row(L("Yeni sürümleri adada haber ver", "Tell me about new versions in the island"), L("Kai günde birkaç kez GitHub'daki sürümlerine bakar; senden hiçbir şey gönderilmez.", "Kai looks at its releases on GitHub a few times a day; nothing about you is sent."), toggle(f.update_checks, (on) => void set("update_checks", on))), row(L("Tanıtım turu", "Tour"), L("AltGr, OK Kai, dikte ve renk, 30 saniyede.", "AltGr, OK Kai, dictation and colour, in 30 seconds."), button(L("Turu tekrar göster", "Show the tour again"), () => showTour(ctx.state, () => void ctx.refresh()), "ghost"))),
    reportCard(),
  );
}

function reportCard(): HTMLElement {
  const note = h("textarea", { class: "a-input wide a-note", rows: "3", placeholder: L("Ne oldu? (isteğe bağlı) Örn: OK Kai dedim, uyanmadı.", "What happened? (optional) E.g. I said OK Kai and it didn't wake.") }) as HTMLTextAreaElement;
  const send = button(L("Hata raporu hazırla", "Prepare a bug report"), async () => {
    send.disabled = true;
    const r = await Api.report(note.value);
    send.disabled = false;
    toast(r ? r.text : L("Rapor hazırlanamadı", "Couldn't prepare the report"));
    if (r) note.value = "";
  }, "primary");
  return card(
    L("Hata raporu", "Bug report"),
    h("p", { class: "a-muted", text: L(
      "Kai'nin loglarını masaüstüne bir zip olarak koyar ve GitHub'da dolu bir hata sayfası açar; zip'i oraya sürüklersin. Söylediklerin ve dikte ettiklerin loglardan çıkarılır, anahtarlar gizlenir. Kai kendisi hiçbir şey göndermez.",
      "Puts Kai's logs in a zip on your Desktop and opens a filled-in GitHub issue to drag it into. What you said or dictated is cut out and keys are masked. Kai sends nothing itself.") }),
    note,
    h("div", { class: "a-inline" }, send),
  );
}

// ── Mascot ──────────────────────────────────────────────────────────────────

export function mascotPage(ctx: Ctx): HTMLElement {
  const i = ctx.state.island;
  const set = async (k: string, v: unknown) => { await Api.set(k, v); await ctx.refresh(); };
  const grid = h("div", { class: "a-mascots" });
  const engines: { engine: BotEngine; canvas: HTMLCanvasElement }[] = [];
  for (const kind of PICKABLE) {
    const canvas = h("canvas", { width: 160, height: 160 }) as HTMLCanvasElement;
    const engine = new BotEngine();
    engine.mascot = kind as Mascot;
    engines.push({ engine, canvas });
    const b = h("button", { class: `a-mascot${i.mascot === kind ? " on" : ""}` }, canvas, h("span", { text: mascotLabel(kind as Mascot) }));
    b.addEventListener("click", () => { engine.squash(); void set("mascot", kind); });
    b.addEventListener("mouseenter", () => engine.blink());
    grid.append(b);
  }
  // Drawn once, then only on hover: sixteen live mascots would be a lot of frames for a settings page.
  const draw = () => {
    for (const { engine, canvas } of engines) {
      const ctx2 = canvas.getContext("2d");
      if (!ctx2) continue;
      engine.update(1 / 30);
      ctx2.setTransform(2, 0, 0, 2, 0, 0);
      ctx2.clearRect(0, 0, 80, 80);
      engine.draw(ctx2, 80, 80);
    }
  };
  draw();
  let raf = 0;
  grid.addEventListener("mouseenter", () => { const loop = () => { draw(); raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop); });
  grid.addEventListener("mouseleave", () => cancelAnimationFrame(raf));

  const swatches = h("div", { class: "a-swatches" }, ...BODY_COLORS.map((c) => {
    const s = h("button", { class: `a-swatch${i.color === c ? " on" : ""}`, style: `background:${c}` });
    s.addEventListener("click", () => { setBodyColor(c); void set("color", c); });
    return s;
  }));
  const hue = h("input", { type: "range", class: "a-hue", min: "0", max: "359" }) as HTMLInputElement;
  hue.addEventListener("input", () => { setBodyColor(hueColor(Number(hue.value))); draw(); });
  hue.addEventListener("change", () => void set("color", hueColor(Number(hue.value))));
  return h(
    "div",
    { class: "a-page" },
    card(L("Maskotun", "Your mascot"), grid),
    card(
      L("Renk", "Colour"),
      h("div", { class: "a-inline" }, swatches, hue),
      h("p", { class: "a-muted", text: L("İlk renk Kai'nin orijinal mavisi.", "The first colour is Kai's original blue.") }),
    ),
    card(
      L("Kostüm", "Outfit"),
      row(L("Gardırop", "Wardrobe"), L("Kostümleri adada, maskota sağ tıklayarak da değiştirebilirsin.", "You can also right-click the mascot on the island."),
        select([[L("Yok", "None"), "none"], [L("Mevsime göre", "Seasonal"), "auto"]], ["none", "auto"].includes(i.outfit) ? i.outfit : "none", (v) => void set("outfit", v))),
    ),
  );
}

// ── Agents ──────────────────────────────────────────────────────────────────

export function agentsPage(ctx: Ctx): HTMLElement {
  const i = ctx.state.island;
  const shown = ctx.state.agents.filter((a) => a.present || a.installed);
  return h(
    "div",
    { class: "a-page" },
    card(
      "Claude Code",
      row(L("Kancalar", "Hooks"), L("Claude Code'un adımları, soruları ve izin istekleri adada görünür.", "Claude Code's steps, questions and permission requests show on the island."), i.hooks ? pill(L("Bağlı", "Connected"), "#2ed47a") : pill(L("Bağlı değil", "Not connected"), "#f4505e")),
    ),
    card(
      L("Claude Desktop sohbetleri", "Claude Desktop chats"),
      row(L("Yanıt hazır olunca haber ver", "Tell me when a reply is ready"), L("Deneysel. Claude uygulaması yazarken başka pencereye geçersen, yanıt bitince Kai zıplar ve Claude Desktop hapı söyler. Sohbetten hiçbir şey okunmaz.", "Experimental. Leave the Claude app while it writes and Kai jumps when the reply is done, on a Claude Desktop pill. Nothing of the chat is read."), toggle(ctx.state.flow.claude_desktop_chat, (on) => void Api.set("claude_desktop_chat", on).then(() => ctx.refresh()))),
    ),
    card(
      L("Diğer ajanlar", "Other agents"),
      shown.length
        ? h("div", { class: "a-list" }, ...shown.map((a) => row(a.name, a.path, toggle(a.installed, async (on) => { await Api.agentSet(a.id, on); await ctx.refresh(); }))))
        : h("p", { class: "a-muted", text: L("Bu bilgisayarda başka ajan bulunamadı.", "No other agents found on this computer.") }),
      i.agentNote ? h("p", { class: "a-muted", text: String(i.agentNote) }) : null,
    ),
  );
}

// ── Chat (the brain) ────────────────────────────────────────────────────────

/**
 * The model's name, with the company's own list as suggestions (Coucou #1000).
 * The saved choice stays as it is, even when it is not in the list.
 */
function modelField(value: string, change: (v: string) => void): HTMLElement {
  const field = input(value, "", change, { wide: true });
  const list = h("datalist", { id: "a-models" });
  field.setAttribute("list", "a-models");
  void Api.listModels().then((names) => {
    list.replaceChildren(...names.map((name) => h("option", { value: name })));
    if (names.length) field.placeholder = L(`${names.length} model, tıkla ve seç`, `${names.length} models, click to pick`);
  });
  return h("div", { class: "a-inline", style: "flex:1" }, field, list);
}

export function chatPage(ctx: Ctx): HTMLElement {
  const b = ctx.state.brain;
  const i = ctx.state.island;
  const set = async (k: string, v: unknown) => { await Api.set(k, v); await ctx.refresh(); };
  const keyName = b.provider === "groq" ? "groq_key" : "api_key";
  const key = input("", b.keys[keyName] ? L("•••••••• (kayıtlı; değiştirmek için yaz)", "•••••••• (saved; type to replace)") : L("anahtarını yapıştır", "paste your key"), async (v) => {
    await Api.secret(keyName, v);
    const verdict = await Api.checkKey();
    toast(verdict === "ok" ? L("Anahtar çalışıyor", "The key works") : verdict === "bad" ? L("Anahtar reddedildi", "The key was refused") : L("Kaydedildi, denenemedi", "Saved, could not test"));
    await ctx.refresh();
  }, { type: "password", wide: true });
  const eleven = input("", b.keys.elevenlabs_key ? "••••••••" : L("isteğe bağlı", "optional"), async (v) => { await Api.secret("elevenlabs_key", v); await ctx.refresh(); }, { type: "password", wide: true });
  return h(
    "div",
    { class: "a-page" },
    card(
      L("Yapay zekâ", "AI"),
      row(L("Sağlayıcı", "Provider"), L("Sohbet, stiller ve not özetleri bununla yazılır.", "Chat, styles and note summaries use it."), select(b.providers.map(([id, name]) => [name, id]), b.provider, (v) => void set("provider", v))),
      row(L("API anahtarı", "API key"), null, key),
      row(L("Model", "Model"), L("Anahtarın çalışıyorsa kullanabileceğin modeller listelenir; istersen adını kendin de yazabilirsin.", "With a working key the models you can use are listed; you can also type a name yourself."), modelField(b.api_model, (v) => void set("api_model", v))),
      b.provider === "custom" ? row(L("Adres", "URL"), null, input(b.api_url, "https://…/v1", (v) => void set("api_url", v), { wide: true })) : null,
    ),
    card(
      L("Ses", "Voice"),
      row(L("Sesli cevap", "Speak answers"), null, toggle(i.speak, (on) => void set("speak", on))),
      row(L("Kai'nin sesi", "Kai's voice"), i.voice === "local:tr" && !ctx.state.models.find((m) => m.id === "voice_tr")?.ready ? L("Bu ses için aşağıdan modeli indir; inene kadar Microsoft'un sesi denenir.", "Download the model below for this voice; until then Microsoft's voice is tried.") : null, select(i.voices, i.voice, (v) => void set("voice", v))),
      modelsGrid(ctx, ["voice_tr"]),
      row(L("Kalite", "Quality"), null, select(i.models, i.model, (v) => void set("model", v))),
      row("ElevenLabs", L("Daha doğal ses için kendi anahtarın.", "Your own key for a more natural voice."), eleven),
      row(L("Sürekli dinle", "Always listen"), L("AltGr'ye basmadan her cümleyi dinler.", "Listens to every sentence without AltGr."), toggle(i.mic, (on) => void set("mic", on))),
    ),
  );
}

// ── OK Kai ──────────────────────────────────────────────────────────────────

export function okKaiPage(ctx: Ctx): HTMLElement {
  const f = ctx.state.flow;
  const wakeReady = ctx.state.models.find((m) => m.id === "wake")?.ready;
  const running = ctx.state.status.ok_kai;
  const examples = [
    L("« OK Kai, Tarkan'dan Kuzu Kuzu çal »", "« OK Kai, play Kuzu Kuzu by Tarkan »"),
    L("« OK Kai, bugün Stripe'tan ne kadar kazandım? »", "« OK Kai, how much did I make on Stripe today? »"),
    L("« OK Kai, ajanlarım ne yapıyor? »", "« OK Kai, what are my agents doing? »"),
    L("« OK Kai, İstanbul'da hava nasıl? »", "« OK Kai, what's the weather in Istanbul? »"),
    L("« OK Kai, Ahmet'e görsel hazır diye e-posta hazırla »", "« OK Kai, draft an email to Ahmet that the image is ready »"),
    L("« OK Kai, Discord'u aç »", "« OK Kai, open Discord »"),
  ];
  return h(
    "div",
    { class: "a-page" },
    card(
      null,
      row("OK Kai", L("« OK Kai » de, sonra ne istediğini söyle. Kai cevabı adada yazar, sesli cevap açıksa söyler.", "Say « OK Kai », then what you want. Kai answers on the island, out loud if speaking is on."),
        toggle(f.ok_kai, async (on) => {
          if (on && !wakeReady) { toast(L("Önce aşağıdan OK Kai modelini indir", "Download the OK Kai model below first")); }
          await Api.set("ok_kai", on);
          await ctx.refresh();
        })),
      f.ok_kai ? row(L("Durum", "Status"), ctx.state.status.ok_kai_error || null, running ? pill(L("Dinliyor", "Listening"), "#2ed47a") : pill(L("Kapalı", "Off"), "#8b90a0")) : null,
      row(L("Hassasiyet", "Sensitivity"), L("Yüksek: daha kolay uyanır, bazen boşuna da uyanır.", "High: wakes more easily, sometimes by mistake."), segmented([[L("Düşük", "Low"), "low"], [L("Orta", "Medium"), "mid"], [L("Yüksek", "High"), "high"]], f.ok_kai_sense, async (v) => { await Api.set("ok_kai_sense", v); await ctx.refresh(); })),
      h("p", { class: "a-muted", text: L("« OK Kai » bilgisayarda duyulur, o ana kadar hiçbir ses dışarı gitmez. Sonraki cümle Whisper indirildiyse yine bilgisayarda yazıya çevrilir; yalnızca o cümlenin metni yapay zekâna gider.", "« OK Kai » is heard on this computer; nothing leaves it before. With Whisper downloaded the request is also transcribed here; only its words go to your AI.") }),
    ),
    card(L("Modeller", "Models"), modelsGrid(ctx, ["wake", "whisper"])),
    card(L("Neler diyebilirsin", "What you can say"), h("ul", { class: "a-examples" }, ...examples.map((e) => h("li", { text: e })))),
    card(L("İsteği yazıya çeviren", "Who transcribes the request"), enginePicker(ctx)),
  );
}

// ── Integrations ────────────────────────────────────────────────────────────

export function integrationsPage(ctx: Ctx): HTMLElement {
  const i = ctx.state.island;
  const b = ctx.state.brain;
  const secret = (k: string) => input("", b.keys[k] ? "••••••••" : L("yapıştır", "paste"), async (v) => { await Api.secret(k, v); await ctx.refresh(); toast(L("Kaydedildi", "Saved")); }, { type: "password", wide: true });
  return h(
    "div",
    { class: "a-page" },
    card(
      L("Haplar", "Pills"),
      row("Spotify", L("Çalanı sistemin medya kontrollerinden okur; müzik çalarken maskot dans eder.", "Read from the system media controls; the mascot dances while music plays."), pill(L("Hazır", "Ready"), "#1DB954")),
      row(L("Hava durumu şehri", "Weather city"), null, input(String(i.city ?? ""), "İstanbul", async (v) => { await Api.set("city", v); await ctx.refresh(); })),
    ),
    card(
      L("Hesaplar", "Accounts"),
      row("GitHub", L("Yıldızlar ve iş akışları için token.", "Token for stars and workflows."), secret("github_token")),
      row("Vercel", L("Dağıtımlar için token.", "Token for deploys."), secret("vercel_token")),
      row("Stripe", L("Bugünkü kazanç için kısıtlı anahtar (rk_).", "Restricted key (rk_) for today's revenue."), secret("stripe_key")),
    ),
    mailCard(ctx),
    calendarCard(ctx),
  );
}

function mailCard(ctx: Ctx): HTMLElement {
  const f = ctx.state.flow;
  const keys = ctx.state.brain.keys;
  const ready = Boolean(f.mail_address && keys.mail_password);
  const test = button(L("Kendime deneme maili at", "Send myself a test"), async () => {
    test.disabled = true;
    const r = await Api.mailTest();
    test.disabled = false;
    toast(r.text || L("Denenemedi", "Could not test"));
  }, "ghost");
  return card(
    L("E-posta", "Email"),
    h("p", { class: "a-muted", text: L(
      "Kai maili hazırlar, sana okur ve « Göndereyim mi? » diye sorar. « Evet » demeden asla göndermez. Bağlamazsan sadece taslak açar.",
      "Kai writes the email, reads it to you and asks « Shall I send it? ». Nothing goes out without your yes. Without this it only opens a draft.") }),
    row(L("Adresin", "Your address"), null, input(f.mail_address, "ornek@gmail.com", async (v) => { await Api.set("mail_address", v); await ctx.refresh(); }, { wide: true })),
    row(L("Uygulama şifresi", "App password"), L("Normal şifren değil. Gmail'de iki adımlı doğrulama açıkken alınır.", "Not your normal password. Gmail gives one once 2-step verification is on."),
      input("", keys.mail_password ? "••••••••" : L("yapıştır", "paste"), async (v) => { await Api.secret("mail_password", v.replace(/\s+/g, "")); await ctx.refresh(); toast(L("Kaydedildi, Windows'ta şifreli duruyor", "Saved, encrypted by Windows")); }, { type: "password", wide: true })),
    h("div", { class: "a-inline" },
      button(L("Gmail uygulama şifresi al", "Get a Gmail app password"), () => void Api.openUrl("https://myaccount.google.com/apppasswords"), "ghost"),
      ready ? test : null),
    row(L("Sunucu (isteğe bağlı)", "Server (optional)"), L("Gmail, Outlook, Yandex, iCloud ve Yahoo kendiliğinden bulunur.", "Gmail, Outlook, Yandex, iCloud and Yahoo are found by themselves."), input(f.mail_server, "smtp.alanadi.com:465", async (v) => { await Api.set("mail_server", v); await ctx.refresh(); })),
  );
}

function calendarCard(ctx: Ctx): HTMLElement {
  const has = ctx.state.brain.keys.calendar_ics;
  const test = button(L("Bugünü göster", "Show today"), async () => { toast(await Api.calendarTest()); }, "ghost");
  return card(
    L("Takvim", "Calendar"),
    h("p", { class: "a-muted", text: L(
      "« Bugün neyim var? », « yarın 3'te toplantı koy ». Kai takvimini okur, hatırlatmalarınla birlikte söyler ve toplantıdan 10 dakika önce haber verir. Ekleme yaparken takvim sayfasını dolu açar, Kaydet'e sen basarsın.",
      "« What's on today? », « add a meeting tomorrow at 3 ». Kai reads your calendar with your reminders and warns you 10 minutes before. To add, it opens the calendar page filled in; you press Save.") }),
    row(L("Gizli iCal adresi", "Secret iCal address"), L("Google Takvim › Ayarlar › takvimin › « iCal biçimindeki gizli adres ». Outlook › Paylaşılan takvimler › Yayımla › ICS.", "Google Calendar › Settings › your calendar › « Secret address in iCal format ». Outlook › Shared calendars › Publish › ICS."),
      input("", has ? "••••••••" : "https://calendar.google.com/…/basic.ics", async (v) => { await Api.secret("calendar_ics", v.trim()); await ctx.refresh(); toast(L("Takvim bağlandı", "Calendar linked")); }, { type: "password", wide: true })),
    h("div", { class: "a-inline" },
      button(L("Google Takvim ayarlarını aç", "Open Google Calendar settings"), () => void Api.openUrl("https://calendar.google.com/calendar/r/settings"), "ghost"),
      has ? test : null),
  );
}

// ── Shortcuts ───────────────────────────────────────────────────────────────

export function shortcutsPage(ctx: Ctx): HTMLElement {
  const key = keyLabel(ctx.state.flow.dictation_key);
  const items: [HTMLElement, string][] = [
    [keycap("AltGr"), L("Basılı tut ve Kai ile konuş", "Hold and talk to Kai")],
    [keycap(...key), L("Basılı tut: dikte (Flow)", "Hold: dictate (Flow)")],
    [keycap(...key, ...key), L("İki kez hızlıca: eller serbest dikte", "Tap twice: hands-free dictation")],
    [keycap("Esc"), L("Dikteyi iptal et", "Cancel dictation")],
    [keycap("Alt", "Shift", "V"), L("Son dikteyi tekrar yapıştır", "Paste the last dictation again")],
    [keycap("Alt", "Shift", "S"), L("Ekrandan bir yer seç ve sor", "Pick part of the screen and ask")],
    [keycap("Alt", "Shift", "T"), L("Ekrandan bir yer seç ve çevir", "Pick part of the screen and translate it")],
    [keycap("Alt", "Shift", "N"), L("Not alıcıyı başlat / durdur", "Start / stop the notetaker")],
    [h("span", { class: "a-kbd", text: "« OK Kai »" }), L("Sesle uyandır (açıksa)", "Wake by voice (when on)")],
  ];
  return h("div", { class: "a-page" }, card(null, h("div", { class: "a-shortcuts" }, ...items.map(([k, t]) => h("div", { class: "a-shortcut" }, k, h("span", { text: t }))))), h("p", { class: "a-muted center", text: L("Dikte tuşunu Dikte sayfasından değiştirebilirsin.", "Change the dictation key on the Dictation page.") }));
}
