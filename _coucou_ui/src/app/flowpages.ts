// Flow pages: Dictation, Statistics, Dictionary, Snippets, Styles.

import { h } from "../views/dom";
import { Api, type AppState, type FlowData, type ModelInfo } from "./api";
import { button, card, input, keycap, L, mb, pill, row, segmented, select, toast, toggle, when } from "./ui";
import { PRESETS, keyLabel, recordButton } from "./keys";

export type Ctx = { state: AppState; flow: FlowData; refresh: () => Promise<void>; go: (page: string) => void };


function glyph(path: string): SVGSVGElement {
  const el = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  el.setAttribute("viewBox", "0 0 24 24");
  el.setAttribute("class", "a-glyph");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", path);
  el.append(p);
  return el;
}

// ── Speech engines, shared by Dictation, the Notetaker and OK Kai ───────────

export function modelCard(m: ModelInfo, onChange: () => void): HTMLElement {
  const bar = h("div", { class: "a-progress" }, h("i", { style: `width:${m.busy && m.size ? Math.min(100, (m.done / m.size) * 100) : m.ready ? 100 : 0}%` }));
  const action = m.ready
    ? button(L("Kaldır", "Remove"), async () => { await Api.modelRemove(m.id); onChange(); }, "ghost")
    : m.busy
      ? button(`${Math.round((m.done / Math.max(1, m.size)) * 100)} %`, () => {}, "ghost")
      : button(L(`İndir · ${mb(m.size)}`, `Download · ${mb(m.size)}`), async () => { await Api.modelDownload(m.id); toast(L("İndirme başladı", "Download started")); onChange(); }, "primary");
  return h(
    "div",
    { class: `a-model${m.ready ? " ready" : ""}` },
    h("div", { class: "a-model-head" }, h("b", { text: m.title }), m.ready ? pill(L("Hazır", "Ready"), "#2ed47a") : null),
    h("div", { class: "a-model-about", text: m.about }),
    m.busy || m.ready ? bar : null,
    m.error ? h("div", { class: "a-error", text: m.error }) : null,
    h("div", { class: "a-model-action" }, action),
  );
}

export function enginePicker(ctx: Ctx): HTMLElement {
  const models = Object.fromEntries(ctx.state.models.map((m) => [m.id, m]));
  const engines: [string, string, string][] = [
    ["online", L("İnternetten", "Online"), L("Groq Whisper, yoksa Google. Ses bilgisayardan çıkar.", "Groq Whisper, else Google. Audio leaves the computer.")],
    ["whisper", "Whisper Turbo", L("Bilgisayarda, Türkçe dahil. İnternet gerekmez.", "On this computer, Turkish included. No internet.")],
    ["parakeet", "Parakeet v3", L("Bilgisayarda, çok hızlı. 25 Avrupa dili; Türkçe yok.", "On this computer, very fast. 25 European languages; no Turkish.")],
  ];
  const wrap = h("div", { class: "a-engines" });
  for (const [id, title, about] of engines) {
    const ok = id === "online" || models[id]?.ready;
    const on = ctx.state.flow.stt_engine === id;
    const el = h(
      "button",
      { class: `a-engine${on ? " on" : ""}${ok ? "" : " off"}` },
      h("b", { text: title }),
      h("span", { text: about }),
      !ok ? h("em", { text: L("Önce modeli indir", "Download the model first") }) : null,
    );
    el.addEventListener("click", async () => {
      if (!ok) { toast(L("Bu motoru seçmek için aşağıdan modeli indir.", "Download the model below to use it.")); return; }
      await Api.set("stt_engine", id);
      await ctx.refresh();
    });
    wrap.append(el);
  }
  return wrap;
}

export function modelsGrid(ctx: Ctx, ids: string[]): HTMLElement {
  const grid = h("div", { class: "a-models" });
  for (const m of ctx.state.models.filter((x) => ids.includes(x.id))) grid.append(modelCard(m, () => void ctx.refresh()));
  return grid;
}

// ── Dictation ───────────────────────────────────────────────────────────────

export function dictationPage(ctx: Ctx): HTMLElement {
  const f = ctx.state.flow;
  const key = keyLabel(f.dictation_key);
  const how = h(
    "div",
    { class: "a-how" },
    h("div", { class: "a-how-step" }, h("span", { class: "a-num", text: "1" }), h("div", {}, keycap(...key), h("p", { text: L("basılı tut", "hold") }))),
    h("div", { class: "a-how-step" }, h("span", { class: "a-num", text: "2" }), h("div", {}, glyph("M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3"), h("p", { text: L("konuş", "speak") }))),
    h("div", { class: "a-how-step" }, h("span", { class: "a-num", text: "3" }), h("div", {}, glyph("M20 5v7a3 3 0 0 1-3 3H5M9 11l-4 4 4 4"), h("p", { text: L("bırak: yazı imlecin yerine gelir", "let go: it's typed where the cursor is") }))),
  );
  const recent = ctx.flow.stats.recent.slice(0, 6);
  return h(
    "div",
    { class: "a-page" },
    card(
      null,
      row(L("Her yerde dikte", "Dictation everywhere"), L("Bir tuşa basılı tut, konuş, bırak; söylediğin imlecin olduğu yere yazılır.", "Hold a key, speak, let go: your words are typed where you are."), toggle(f.dictation, async (on) => { await Api.set("dictation", on); await ctx.refresh(); })),
      how,
      row(L("Dikte tuşu", "Dictation key"), L("AltGr Kai ile konuşmak için ayrıldı. Kendi kısayolunda tuşlara birlikte basıp bırak, en fazla dört tuş.", "AltGr is kept for talking to Kai. For your own shortcut press the keys together and let go, up to four."),
        h("div", { class: "a-inline" },
          select([
            ...PRESETS.map(([v, tr]): [string, string] => [L(tr, tr.replace("Sol", "Left").replace("Sağ", "Right")), v]),
            ...(f.dictation_key.startsWith("keys:") ? [[keyLabel(f.dictation_key).join(" + "), f.dictation_key] as [string, string]] : []),
          ], f.dictation_key, async (v) => { await Api.set("dictation_key", v); await ctx.refresh(); }),
          recordButton(async (v) => { await Api.set("dictation_key", v); await ctx.refresh(); toast(L("Dikte kısayolu kaydedildi", "Dictation shortcut saved")); }))),
      h(
        "div",
        { class: "a-tips" },
        h("div", {}, keycap(...key), h("span", { text: L(" iki kez hızlıca: eller serbest, bir kez daha basınca biter", " tapped twice: hands-free until the next tap") })),
        h("div", {}, keycap("Esc"), h("span", { text: L(" dikteyi iptal eder", " cancels") })),
        h("div", {}, keycap("Alt", "Shift", "V"), h("span", { text: L(" son dikteyi tekrar yapıştırır", " pastes the last dictation again") })),
      ),
      row(L("Konuşurken diğer sesler sussun", "Quiet while you speak"), L("Kai seni dinlerken müzik, video ve görüşmeler susar; duyunca sesleri geri gelir. Kai'nin kendi sesi ve senin kapattıkların dokunulmaz.", "While Kai listens, music, videos and calls go quiet and come back once it has heard you. Kai's own sound and what you muted yourself stay as they are."), toggle(f.mute_others, async (on) => { await Api.set("mute_others", on); await ctx.refresh(); })),
      row(L("Son dikteyi yapıştır", "Paste the last dictation"), L("Yazı alanı yoksa metin panoda kalır; buradan da yapıştırabilirsin.", "When no text field had the focus, it stays on the clipboard."), button(L("Yapıştır", "Paste"), () => void Api.pasteLast(), "ghost")),
    ),
    card(L("Ses tanıma", "Speech recognition"), enginePicker(ctx), modelsGrid(ctx, ["whisper", "parakeet"])),
    card(
      L("Son dikteler", "Recent dictations"),
      recent.length
        ? h("div", { class: "a-list" }, ...recent.map((r) => h("div", { class: "a-list-row" }, h("span", { class: "a-muted", text: `${when(r.at)} · ${r.app || "?"}` }), h("span", { text: r.text }))))
        : h("p", { class: "a-muted", text: L("Henüz dikte yok. Dikteyi aç, tuşa basılı tutup konuş.", "No dictation yet. Turn it on, hold the key and speak.") }),
    ),
  );
}

// ── Statistics ──────────────────────────────────────────────────────────────

export function statsPage(ctx: Ctx): HTMLElement {
  const s = ctx.flow.stats;
  const minutes = Math.round(s.saved_seconds / 60);
  const tiles = h(
    "div",
    { class: "a-tiles" },
    tile(String(s.words.toLocaleString()), L("kelime", "words")),
    tile(minutes >= 60 ? `${(minutes / 60).toFixed(1)} sa` : `${minutes} dk`, L("kazanılan süre", "time saved")),
    tile(s.wpm ? `${s.wpm}` : "–", L("kelime / dakika", "words / minute")),
    tile(String(s.dictations), L("dikte", "dictations")),
  );
  const top = Math.max(1, ...s.days.map((d) => d.words));
  const chart = h(
    "div",
    { class: "a-chart" },
    ...s.days.map((d) =>
      h(
        "div",
        { class: "a-bar", title: `${d.day}: ${d.words}` },
        h("i", { style: `height:${Math.max(2, (d.words / top) * 100)}%` }),
        h("span", { text: d.day.slice(8) }),
      ),
    ),
  );
  const appTop = Math.max(1, ...s.apps.map((a) => a.words));
  const apps = h(
    "div",
    { class: "a-apps" },
    ...s.apps.map((a) => h("div", { class: "a-app-row" }, h("span", { text: a.app.replace(/\.exe$/, "") }), h("div", { class: "a-app-bar" }, h("i", { style: `width:${(a.words / appTop) * 100}%` })), h("b", { text: String(a.words) }))),
  );
  const keep: [string, string][] = [[L("Hep", "Forever"), "0"], [L("90 gün", "90 days"), "90"], [L("30 gün", "30 days"), "30"], [L("7 gün", "7 days"), "7"], [L("1 gün", "1 day"), "1"]];
  return h(
    "div",
    { class: "a-page" },
    tiles,
    card(L("Günlük kelime (son 14 gün)", "Words per day (last 14 days)"), chart),
    card(L("Dikte ettiğin uygulamalar", "Where you dictate"), s.apps.length ? apps : h("p", { class: "a-muted", text: "–" })),
    card(
      L("Geçmiş", "History"),
      row(L("Ne kadar saklansın", "Keep it for"), L("Geçmiş yalnızca bu bilgisayarda durur.", "History stays on this computer."), segmented(keep, String(ctx.flow.settings.keep_days), async (v) => { await Api.flowSet("settings", { keep_days: Number(v) }); await ctx.refresh(); })),
      row(L("Geçmişi sil", "Clear history"), null, button(L("Sil", "Clear"), async () => { await Api.flowSet("clear_history", null); toast(L("Geçmiş silindi", "History cleared")); await ctx.refresh(); }, "danger")),
    ),
  );
}

function tile(big: string, small: string): HTMLElement {
  return h("div", { class: "a-tile" }, h("b", { text: big }), h("span", { text: small }));
}

// ── Dictionary ──────────────────────────────────────────────────────────────

export function dictionaryPage(ctx: Ctx): HTMLElement {
  let items = [...ctx.flow.dictionary];
  const save = async () => { await Api.flowSet("dictionary", items); await ctx.refresh(); };
  const names = items.filter((i): i is { word: string } => "word" in i);
  const swaps = items.filter((i): i is { from: string; to: string } => "from" in i);
  const chips = h("div", { class: "a-chips" }, ...names.map((n) => {
    const x = h("button", { class: "a-chip", text: `${n.word}  ✕` });
    x.addEventListener("click", () => { items = items.filter((i) => i !== n); void save(); });
    return x;
  }));
  const word = input("", L("örn. Kai, Ayşe, Claude Code", "e.g. Kai, Claude Code"), () => {});
  const addWord = button(L("Ekle", "Add"), () => {
    const v = word.value.trim();
    if (!v) return;
    items.push({ word: v });
    void save();
  }, "primary");
  word.addEventListener("keydown", (e) => { if (e.key === "Enter") addWord.click(); });
  const from = input("", L("duyulan: klod kod", "heard: cloud code"), () => {});
  const to = input("", L("yazılacak: Claude Code", "written: Claude Code"), () => {});
  const addSwap = button(L("Ekle", "Add"), () => {
    if (!from.value.trim() || !to.value.trim()) return;
    items.push({ from: from.value.trim(), to: to.value.trim() });
    void save();
  }, "primary");
  const list = h("div", { class: "a-list" }, ...swaps.map((s) => {
    const del = button("✕", () => { items = items.filter((i) => i !== s); void save(); }, "ghost");
    return h("div", { class: "a-list-row swap" }, h("span", { class: "a-muted", text: s.from }), h("span", { text: "→" }), h("b", { text: s.to }), del);
  }));
  return h(
    "div",
    { class: "a-page" },
    card(L("İsimler", "Names"), h("p", { class: "a-muted", text: L("Kai bu isimleri hep yazıldığı gibi yazar. Ses tanımaya da ipucu olarak gider.", "Kai always spells these as written; they're also a hint for recognition.") }), chips, h("div", { class: "a-inline" }, word, addWord)),
    card(L("Değiştirmeler", "Replacements"), h("p", { class: "a-muted", text: L("Bir söz hep yanlış çıkıyorsa doğrusunu yaz.", "When something always comes out wrong, write what it should be.") }), list, h("div", { class: "a-inline" }, from, to, addSwap)),
  );
}

// ── Snippets ────────────────────────────────────────────────────────────────

export function snippetsPage(ctx: Ctx): HTMLElement {
  let items = [...ctx.flow.snippets];
  const save = async () => { await Api.flowSet("snippets", items); await ctx.refresh(); };
  const list = h("div", { class: "a-snips" }, ...items.map((s) => {
    const del = button(L("Sil", "Delete"), () => { items = items.filter((x) => x !== s); void save(); }, "ghost");
    return h("div", { class: "a-snip" }, h("div", { class: "a-snip-head" }, h("b", { text: `« ${s.trigger} »` }), del), h("pre", { text: s.text }));
  }));
  const trigger = input("", L("söylenecek söz: imzam", "what you say: my signature"), () => {}, { wide: true });
  const body = h("textarea", { class: "a-textarea", rows: 5, placeholder: L("yapıştırılacak metin, olduğu gibi", "the text to paste, untouched") }) as HTMLTextAreaElement;
  const add = button(L("Kısayol ekle", "Add snippet"), () => {
    if (!trigger.value.trim() || !body.value.trim()) return;
    items.push({ trigger: trigger.value.trim(), text: body.value });
    void save();
  }, "primary");
  return h(
    "div",
    { class: "a-page" },
    card(null, h("p", { class: "a-muted", text: L("Dikte ederken yalnızca kısayolun sözünü söyle; bütün metin hiç dokunulmadan yapıştırılır.", "Say only the snippet's phrase while dictating: the whole text is pasted untouched.") }), trigger, body, h("div", { class: "a-inline end" }, add)),
    items.length ? card(L("Kısayolların", "Your snippets"), list) : null,
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────

export function stylesPage(ctx: Ctx): HTMLElement {
  const st = ctx.flow.styles;
  const save = async (data: Partial<typeof st>) => { await Api.flowSet("styles", data); await ctx.refresh(); };
  const looks: [string, string, string, string][] = [
    ["as_said", L("Söylendiği gibi", "As said"), L("Dokunulmaz.", "Untouched."), L("ee yarın yok perşembe gelirim", "um tomorrow no thursday I'll come")],
    ["natural", L("Doğal", "Natural"), L("Dolgular ve tekrarlar gider, düzeltmelerin uygulanır.", "Fillers and repeats go, your corrections are applied."), L("Perşembe gelirim.", "I'll come on Thursday.")],
    ["polished", L("Cilalı", "Polished"), L("Dilbilgisi ve noktalama düzelir, paragraflara bölünür.", "Grammar and punctuation fixed, split into paragraphs."), L("Perşembe günü geleceğim.", "I will come on Thursday.")],
  ];
  const cards = h("div", { class: "a-styles" }, ...looks.map(([id, title, about, example]) => {
    const b = h("button", { class: `a-style${st.default === id ? " on" : ""}` }, h("b", { text: title }), h("span", { text: about }), h("em", { text: `“${example}”` }));
    b.addEventListener("click", () => void save({ default: id }));
    return b;
  }));
  const apps = Object.entries(st.apps);
  const opts: [string, string][] = looks.map(([id, title]) => [title, id]);
  const appRows = h("div", { class: "a-list" }, ...apps.map(([app, style]) =>
    h("div", { class: "a-list-row swap" }, h("b", { text: app }), segmented(opts, style, (v) => void save({ apps: { ...st.apps, [app]: v } })), button("✕", () => { const next = { ...st.apps }; delete next[app]; void save({ apps: next }); }, "ghost")),
  ));
  const appName = input("", L("uygulama: chrome.exe, slack.exe…", "app: chrome.exe, slack.exe…"), () => {});
  const addApp = button(L("Ekle", "Add"), () => {
    const v = appName.value.trim().toLowerCase();
    if (!v) return;
    void save({ apps: { ...st.apps, [v.endsWith(".exe") ? v : `${v}.exe`]: "polished" } });
  }, "primary");
  const sample = h("textarea", { class: "a-textarea", rows: 3, placeholder: L("Denemek için bir şey yaz: “ee yarın, yok perşembe toplantı yapalım ııı saat üçte”", "Type something to try") }) as HTMLTextAreaElement;
  const out = h("div", { class: "a-tryout" });
  const tryIt = button(L("Dene", "Try"), async () => {
    out.textContent = "…";
    out.textContent = await Api.tryStyle(sample.value, st.default);
  }, "ghost");
  return h(
    "div",
    { class: "a-page" },
    card(
      null,
      row(L("Claude ile temizle", "Clean up with Claude"), L("Seçtiğin yapay zekâ ve kendi anahtarınla. Kapalıyken söylediğin gibi yapıştırılır.", "With your chosen model and your own key. Off: pasted as said."), toggle(st.enabled, (on) => void save({ enabled: on }))),
      !ctx.state.island.api ? h("p", { class: "a-warn", text: L("Önce Sohbet sayfasından bir yapay zekâ anahtarı ekle.", "Add an AI key on the Chat page first.") }) : null,
    ),
    card(L("Varsayılan stil", "Default style"), cards),
    card(L("Uygulamaya göre", "Per app"), apps.length ? appRows : h("p", { class: "a-muted", text: L("Örneğin e-postada cilalı, sohbette doğal.", "e.g. polished in mail, natural in chat.") }), h("div", { class: "a-inline" }, appName, addApp)),
    card(L("Dene", "Try it"), sample, h("div", { class: "a-inline end" }, tryIt), out),
  );
}
