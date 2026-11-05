// The first-open tour: five short steps over the Kai window, with the user's
// own mascot acting each one out. Shown once; General › "Show the tour again".

import { BotEngine } from "../mochi/engine";
import { parseMascot } from "../mochi/mascots";
import { BODY_COLORS, setBodyColor } from "../mochi/palette";
import { h } from "../views/dom";
import { Api, type AppState } from "./api";
import { keycap, L } from "./ui";
import { keyLabel } from "./keys";

interface Step { title: () => string; text: () => string; visual: () => HTMLElement; act: (bot: BotEngine, t: number) => void }

export function showTour(state: AppState, done: () => void) {
  const bot = new BotEngine();
  bot.mascot = parseMascot(String(state.island.mascot));
  const dictKey = keyLabel(state.flow.dictation_key);
  let color = String(state.island.color || BODY_COLORS[0]);

  const swatches = () => h("div", { class: "a-swatches" }, ...BODY_COLORS.map((c) => {
    const s = h("button", { class: `a-swatch${c === color ? " on" : ""}`, style: `background:${c}` });
    s.addEventListener("click", () => {
      color = c;
      setBodyColor(c);
      bot.squash();
      s.parentElement?.querySelectorAll(".a-swatch").forEach((x) => x.classList.toggle("on", x === s));
      void Api.set("color", c);
    });
    return s;
  }));

  const steps: Step[] = [
    {
      title: () => L("Selam, ben Kai", "Hi, I'm Kai"),
      text: () => L("Ekranın üstündeki adada yaşıyorum. 30 saniyede neler yaptığımı göstereyim.", "I live on the island at the top of your screen. Let me show you what I do in 30 seconds."),
      visual: () => h("div"),
      act: (b) => { b.voiceTarget = 0; },
    },
    {
      title: () => L("AltGr: benimle konuş", "AltGr: talk to me"),
      text: () => L("AltGr'yi basılı tut, ne istediğini söyle, bırak. Şarkı çalarım, uygulama açarım, soruna cevap veririm.", "Hold AltGr, say what you want, let go. I play songs, open apps and answer questions."),
      visual: () => keycap("AltGr"),
      // The mascot bounces as if hearing a voice, like it does on the island.
      act: (b, t) => { b.voiceTarget = Math.max(0, Math.sin(t * 9) * 0.5 + Math.sin(t * 23) * 0.3); },
    },
    {
      title: () => "OK Kai",
      text: () => L("Tuşa bile basma: « OK Kai » de, sonra iste. Uyandırma sözü bilgisayarında duyulur, ses dışarı gitmez.", "Don't even press a key: say « OK Kai », then ask. The wake word is heard on your computer; no audio leaves it."),
      visual: () => h("span", { class: "a-kbd", text: "« OK Kai »" }),
      act: (b, t) => { b.voiceTarget = t % 2.4 < 0.5 ? 0.8 : 0; },
    },
    {
      title: () => L("Dikte: her yerde yaz", "Dictation: type anywhere"),
      text: () => L("Bu tuşu basılı tut ve konuş; söylediğin imlecin olduğu yere yazılır. İki kez hızlıca basarsan eller serbest.", "Hold this key and speak; your words are typed where the cursor is. Tap twice for hands-free."),
      visual: () => keycap(...dictKey),
      act: (b) => { b.voiceTarget = 0; },
    },
    {
      title: () => L("Rengimi sen seç", "Pick my colour"),
      text: () => L("İlki benim orijinal mavim. Sonra Maskot sayfasından on altı maskottan birini de seçebilirsin.", "The first is my original blue. On the Mascot page you can pick one of sixteen mascots too."),
      visual: swatches,
      act: (b) => { b.voiceTarget = 0; },
    },
  ];

  let at = 0;
  const canvas = h("canvas", { class: "a-tour-bot", width: 240, height: 240 }) as HTMLCanvasElement;
  const title = h("h2", { class: "a-tour-title" });
  const text = h("p", { class: "a-tour-text" });
  const visual = h("div", { class: "a-tour-visual" });
  const dots = h("div", { class: "a-tour-dots" });
  const back = h("button", { class: "a-btn ghost", text: L("Geri", "Back") }) as HTMLButtonElement;
  const next = h("button", { class: "a-btn primary" }) as HTMLButtonElement;
  const skip = h("button", { class: "a-tour-skip", text: L("Atla", "Skip") });
  const box = h("div", { class: "a-tour-card", role: "dialog", "aria-modal": "true" }, canvas, title, text, visual, h("div", { class: "a-tour-foot" }, dots, h("div", { class: "a-inline" }, back, next)), skip);
  const veil = h("div", { class: "a-tour" }, box);

  const show = () => {
    const s = steps[at];
    title.textContent = s.title();
    text.textContent = s.text();
    visual.replaceChildren(s.visual());
    dots.replaceChildren(...steps.map((_x, i) => h("span", { class: i === at ? "on" : "" })));
    back.style.visibility = at ? "visible" : "hidden";
    next.textContent = at === steps.length - 1 ? L("Başlayalım", "Let's go") : L("İleri", "Next");
    bot.squash();
    box.classList.remove("in");
    void box.offsetWidth;
    box.classList.add("in");
  };

  let raf = 0;
  let last = performance.now();
  let clock = 0;
  const loop = (now: number) => {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    clock += dt;
    steps[at].act(bot, clock);
    bot.update(dt);
    const x = canvas.getContext("2d");
    if (x) {
      x.setTransform(2, 0, 0, 2, 0, 0);
      x.clearRect(0, 0, 120, 120);
      bot.draw(x, 120, 120);
    }
    raf = requestAnimationFrame(loop);
  };

  const close = () => {
    cancelAnimationFrame(raf);
    document.removeEventListener("keydown", keys);
    veil.classList.add("out");
    window.setTimeout(() => veil.remove(), 220);
    void Api.set("tour_done", true);
    done();
  };
  const keys = (e: KeyboardEvent) => {
    // Enter on a focused button already clicks it; only arrows and Enter elsewhere step here.
    const onButton = (e.target as HTMLElement | null)?.tagName === "BUTTON";
    if (e.key === "Escape") close();
    else if (e.key === "ArrowRight" || (e.key === "Enter" && !onButton)) next.click();
    else if (e.key === "ArrowLeft" && at) back.click();
  };

  next.addEventListener("click", () => { if (at === steps.length - 1) close(); else { at++; show(); } });
  back.addEventListener("click", () => { if (at) { at--; show(); } });
  skip.addEventListener("click", close);
  document.addEventListener("keydown", keys);

  document.body.append(veil);
  show();
  next.focus();
  raf = requestAnimationFrame(loop);
}
