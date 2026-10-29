// The Kai window: a sidebar of pages, a band of walking mascots on top of each,
// and particles behind. Pages are rebuilt from the host's state whenever it
// changes; the status (recording, downloads) is polled while it matters.

import "./app.css";
import { parseMascot } from "../mochi/mascots";
import { setBodyColor } from "../mochi/palette";
import { BotEngine } from "../mochi/engine";
import { h, clear } from "../views/dom";
import { Api, ready, type AppState, type FlowData } from "./api";
import { Band, Particles } from "./band";
import { dictationPage, dictionaryPage, snippetsPage, statsPage, stylesPage, type Ctx } from "./flowpages";
import { agentsPage, chatPage, generalPage, integrationsPage, mascotPage, okKaiPage, shortcutsPage } from "./kaipages";
import { notesPage } from "./notespage";
import { feedbackPage } from "./feedbackpage";
import { showTour } from "./tour";
import { L, setTurkish } from "./ui";

interface Page { id: string; group: "flow" | "kai"; title: () => string; sub: () => string; color: string; icon: string }

const PAGES: Page[] = [
  { id: "dictation", group: "flow", title: () => L("Dikte", "Dictation"), sub: () => L("Konuş, imlecin olduğu yere yazılsın.", "Speak, and it's typed where you are."), color: "#35b8ff", icon: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3" },
  { id: "notes", group: "flow", title: () => L("Not alıcı", "Notetaker"), sub: () => L("Görüşmeyi kaydet; döküm, özet ve yapılacaklar hazır.", "Record a call; transcript, summary and to-dos."), color: "#ff5a64", icon: "M5 4h14v16H5zM9 9h6M9 13h6M9 17h3" },
  { id: "stats", group: "flow", title: () => L("İstatistik", "Statistics"), sub: () => L("Kaç kelime, ne kadar zaman kazandın.", "Words, and the time you saved."), color: "#2ed47a", icon: "M5 20V10M10 20V4M15 20v-7M20 20v-4" },
  { id: "dictionary", group: "flow", title: () => L("Sözlük", "Dictionary"), sub: () => L("İsimler doğru yazılsın, yanlışlar düzelsin.", "Names spelled right, mistakes fixed."), color: "#f5a524", icon: "M5 4h10a4 4 0 0 1 4 4v12H9a4 4 0 0 1-4-4zM9 8h6" },
  { id: "snippets", group: "flow", title: () => L("Kısayol metinleri", "Snippets"), sub: () => L("Kısa bir söz, koca bir metin.", "A short phrase, a whole text."), color: "#c792ea", icon: "M8 6l-5 6 5 6M16 6l5 6-5 6" },
  { id: "styles", group: "flow", title: () => L("Stiller", "Styles"), sub: () => L("Metin uygulamaya göre temizlensin.", "Text cleaned up per app."), color: "#ff8a5c", icon: "M4 20l4-1L19 8l-3-3L5 16zM14 7l3 3" },
  { id: "general", group: "kai", title: () => L("Genel", "General"), sub: () => L("Dil, açılış ve sesler.", "Language, startup and sounds."), color: "#8b90a0", icon: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v3M12 19v3M2 12h3M19 12h3" },
  { id: "mascot", group: "kai", title: () => L("Maskot", "Mascot"), sub: () => L("On altı maskot, istediğin renk.", "Sixteen mascots, any colour."), color: "#35b8ff", icon: "M5 12a7 8 0 0 1 14 0v8l-2-1.5L15 20l-3-1.5L9 20l-2-1.5L5 20zM10 11h.01M14 11h.01" },
  { id: "agents", group: "kai", title: () => L("Ajanlar", "Agents"), sub: () => L("Claude Code ve diğerleri adada.", "Claude Code and others on the island."), color: "#f55f47", icon: "M4 6h16v10H4zM8 20h8M9 10l2 2-2 2M13 14h3" },
  { id: "chat", group: "kai", title: () => L("Sohbet", "Chat"), sub: () => L("Kai'nin beyni ve sesi.", "Kai's brain and voice."), color: "#6c8cff", icon: "M4 5h16v11H9l-5 4z" },
  { id: "okkai", group: "kai", title: () => "OK Kai", sub: () => L("Adını söyle, iste.", "Say its name, ask."), color: "#2ee6d6", icon: "M12 4v16M8 8v8M16 8v8M4 11v2M20 11v2" },
  { id: "integrations", group: "kai", title: () => L("Entegrasyonlar", "Integrations"), sub: () => L("E-posta, takvim, Spotify, GitHub, Stripe.", "Email, calendar, Spotify, GitHub, Stripe."), color: "#1DB954", icon: "M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1" },
  { id: "feedback", group: "kai", title: () => L("İstek ve değerlendirme", "Rating & wishes"), sub: () => L("Bu sürüme puan ver, sonrakinde ne olsun söyle.", "Rate this version, say what comes next."), color: "#ffd666", icon: "M12 2.6l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.5l-5.9 3.1 1.2-6.5L2.5 9.5l6.6-.9z" },
  { id: "shortcuts", group: "kai", title: () => L("Kısayollar", "Shortcuts"), sub: () => L("Hepsi bir arada.", "All in one place."), color: "#f4f5f7", icon: "M3 7h18v10H3zM7 11h1M11 11h2M16 11h1M7 14h10" },
];

let state: AppState | null = null;
let flowData: FlowData | null = null;
let current = "dictation";
let noteList: { id: string; title: string; started: number; seconds: number }[] = [];

const root = document.getElementById("app-root")!;
const band = new Band();
const particles = new Particles(document.getElementById("app-particles") as HTMLCanvasElement);

function icon(path: string): SVGSVGElement {
  const el = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  el.setAttribute("viewBox", "0 0 24 24");
  el.setAttribute("width", "17");
  el.setAttribute("height", "17");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", path);
  p.setAttribute("fill", "none");
  p.setAttribute("stroke", "currentColor");
  p.setAttribute("stroke-width", "1.7");
  p.setAttribute("stroke-linecap", "round");
  p.setAttribute("stroke-linejoin", "round");
  el.append(p);
  return el;
}

// The sidebar's own mascot: the user's, in the user's colour, breathing.
const logoCanvas = h("canvas", { class: "a-logo-bot", width: 96, height: 96 }) as HTMLCanvasElement;
const logoBot = new BotEngine();

async function refresh() {
  const [s, f] = await Promise.all([Api.state(), Api.flow()]);
  if (s) state = s;
  if (f) flowData = f;
  if (current === "notes") noteList = await Api.notes();
  render();
}

function go(page: string) {
  current = page;
  void refresh();
}
(window as unknown as { __kaiPage?: (p: string) => void }).__kaiPage = (p: string) => go(p);

function render() {
  if (!state || !flowData) return;
  setTurkish(state.language !== "en");
  setBodyColor(state.island.color);
  logoBot.mascot = parseMascot(state.island.mascot);
  const page = PAGES.find((p) => p.id === current) ?? PAGES[0];
  document.documentElement.style.setProperty("--page", page.color);
  particles.color = page.color;

  const nav = h("nav", { class: "a-nav" },
    h("div", { class: "a-brand" }, logoCanvas, h("div", {}, h("b", { text: "Kai" }), h("span", { text: `v${state.update.current || state.island.version}` }))),
  );
  for (const group of ["flow", "kai"] as const) {
    nav.append(h("div", { class: "a-nav-group", text: group === "flow" ? "FLOW" : "KAI" }));
    for (const p of PAGES.filter((x) => x.group === group)) {
      const b = h("button", { class: `a-nav-item${p.id === page.id ? " on" : ""}`, style: `--c:${p.color}` }, icon(p.icon), h("span", { text: p.title() }));
      b.addEventListener("click", () => go(p.id));
      nav.append(b);
    }
  }
  const rec = state.status.recorder;
  if (rec?.recording) {
    const r = h("button", { class: "a-nav-rec" }, h("i", {}), h("span", { text: L("Kayıt sürüyor", "Recording") }));
    r.addEventListener("click", () => go("notes"));
    nav.append(r);
  }

  const ctx: Ctx = { state, flow: flowData, refresh, go };
  let body: HTMLElement;
  switch (page.id) {
    case "notes": body = notesPage(ctx, noteList); break;
    case "stats": body = statsPage(ctx); break;
    case "dictionary": body = dictionaryPage(ctx); break;
    case "snippets": body = snippetsPage(ctx); break;
    case "styles": body = stylesPage(ctx); break;
    case "general": body = generalPage(ctx); break;
    case "mascot": body = mascotPage(ctx); break;
    case "agents": body = agentsPage(ctx); break;
    case "chat": body = chatPage(ctx); break;
    case "okkai": body = okKaiPage(ctx); break;
    case "integrations": body = integrationsPage(ctx); break;
    case "shortcuts": body = shortcutsPage(ctx); break;
    case "feedback": body = feedbackPage(ctx); break;
    default: body = dictationPage(ctx);
  }
  const header = h("header", { class: "a-head" }, band.el, h("div", { class: "a-head-text" }, h("h1", { text: page.title() }), h("p", { text: page.sub() })));
  const main = h("main", { class: "a-main" }, header, body);
  const scroll = root.querySelector(".a-main")?.scrollTop ?? 0;
  const samePage = root.dataset.page === page.id;
  clear(root);
  root.dataset.page = page.id;
  root.append(nav, main);
  if (samePage) main.scrollTop = scroll;
  if (!samePage || !band.el.dataset.page) {
    band.el.dataset.page = page.id;
    requestAnimationFrame(() => band.setup(page.color, parseMascot(state?.island.mascot)));
  }
}

// One loop for the band, the particles and the sidebar mascot. Thirty frames a
// second while the window is in front; none at all while it is behind another
// window or minimised. At the display's own rate it kept the GPU busy.
let last = performance.now();
let looping = false;
let pace: number | null = null;
let touched = performance.now();
let tick = 0;
// In front and used in the last minute: someone is looking.
const awake = () => !document.hidden && document.hasFocus() && performance.now() - touched < 60000;
function frame(now: number) {
  const dt = Math.min(0.08, (now - last) / 1000);
  last = now;
  tick += 1;
  band.step(dt);
  // The specks drift slowly: every other frame is plenty.
  if (tick % 2 === 0) particles.step(dt * 2);
  const ctx2 = logoCanvas.getContext("2d");
  if (ctx2) {
    logoBot.update(dt);
    ctx2.setTransform(2, 0, 0, 2, 0, 0);
    ctx2.clearRect(0, 0, 48, 48);
    logoBot.draw(ctx2, 48, 48);
  }
  if (!awake()) {
    looping = false;
    return;
  }
  // Thirty frames a second while the pointer moves, fifteen when it rests.
  pace = window.setTimeout(() => {
    pace = null;
    requestAnimationFrame(frame);
  }, performance.now() - touched < 8000 ? 28 : 62);
}
function wake() {
  touched = performance.now();
  if (looping || !awake()) return;
  looping = true;
  last = performance.now();
  if (pace != null) window.clearTimeout(pace);
  requestAnimationFrame(frame);
}
window.addEventListener("focus", wake);
document.addEventListener("visibilitychange", wake);
window.addEventListener("pointermove", wake);
window.addEventListener("keydown", wake);
window.addEventListener("wheel", wake, { passive: true });

/** While something moves on the host (a recording, a download), its status is asked for every second. */
async function poll() {
  const s = await Api.status();
  if (s && state) {
    const before = JSON.stringify([state.status, state.models]);
    state.status = s.status;
    state.models = s.models;
    const after = JSON.stringify([state.status, state.models]);
    if (before !== after) {
      const recorder = s.status.recorder;
      // A recording that just finished brings its note to the list.
      if (current === "notes" && recorder && !recorder.processing) noteList = await Api.notes();
      // Not while something is being typed: a re-render would drop it.
      const typing = document.activeElement?.matches("input, textarea") ?? false;
      if (!typing && (["dictation", "notes", "okkai", "integrations", "chat"].includes(current) || recorder?.recording)) render();
    }
  }
  const busy = state?.status.recorder?.recording || state?.status.recorder?.processing || state?.models.some((m) => m.busy);
  window.setTimeout(poll, busy ? 1000 : 3000);
}

async function main() {
  await ready();
  await refresh();
  if (state && !state.flow.tour_done) showTour(state, () => void refresh());
  // One frame drawn even when the window opens behind another, then the loop waits for focus.
  requestAnimationFrame(frame);
  looping = true;
  void poll();
  window.addEventListener("focus", () => void refresh());
}

void main();
