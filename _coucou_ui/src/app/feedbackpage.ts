// Rating & wishes: five stars for this version and a line about what to add
// next. The mascot feels the stars (sad at one, hearts at five). Sending is a
// little film on the stage above the form: the form folds into a letter, grass
// grows, Kai gets football boots, runs, kicks the letter into space, waves,
// walks back, and everything is as it was. The developer's Kai receives it as
// a note (feedback.py).

import { BotEngine } from "../mochi/engine";
import { parseMascot } from "../mochi/mascots";
import { h } from "../views/dom";
import { Api } from "./api";
import type { Ctx } from "./flowpages";
import { card, L, toast } from "./ui";

const STAGE_H = 230;
const BOT = 118;
const SEND_S = 5.9;
const STAR_PATH = "M12 2.6l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.5l-5.9 3.1 1.2-6.5L2.5 9.5l6.6-.9z";

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
const span = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));
const easeOut = (p: number) => 1 - Math.pow(1 - p, 3);
const easeInOut = (p: number) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const back = (p: number) => 1 + 2.7 * Math.pow(p - 1, 3) + 1.7 * Math.pow(p - 1, 2);
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

interface Spark { x: number; y: number; born: number }

let page: HTMLElement | null = null;

export function feedbackPage(ctx: Ctx): HTMLElement {
  // The page is kept between visits and refreshes: a refresh in the middle of
  // the film would otherwise cut it, and wipe a half-written wish.
  const kept = page as unknown as { __engine?: BotEngine; __start?: () => void } | null;
  if (page && kept?.__engine) {
    kept.__engine.mascot = parseMascot(ctx.state.island.mascot);
    requestAnimationFrame(() => kept.__start?.());
    void (kept as { __inbox?: (fetch: boolean) => Promise<void> }).__inbox?.(false);
    return page;
  }
  page = build(ctx);
  return page;
}

function build(ctx: Ctx): HTMLElement {
  const engine = new BotEngine();
  engine.mascot = parseMascot(ctx.state.island.mascot);
  const stage = h("canvas", { class: "a-fb-stage" }) as HTMLCanvasElement;

  let stars = 0;
  let hover = 0;
  let sending = false;
  let t0 = 0;
  let result: Promise<{ ok: boolean; error: string }> | null = null;
  let sparks: Spark[] = [];
  let greeted = false;
  let kicked = false;
  let droop = 0;
  let nextMood = 0;

  // ── The form ─────────────────────────────────────────────────────────────
  const starButtons = [1, 2, 3, 4, 5].map((n) => {
    const b = h("button", { class: "a-fb-star", title: `${n}`, "aria-label": `${n}` });
    b.innerHTML = `<svg viewBox="0 0 24 24" width="30" height="30"><path d="${STAR_PATH}"/></svg>`;
    b.addEventListener("mouseenter", () => { hover = n; feel(n); paint(); });
    b.addEventListener("click", () => { stars = n; feel(n, true); paint(); });
    return b;
  });
  const starRow = h("div", { class: "a-fb-stars" }, ...starButtons);
  starRow.addEventListener("mouseleave", () => { hover = 0; feel(stars); paint(); });
  const caption = h("div", { class: "a-fb-caption" });
  const text = h("textarea", {
    class: "a-textarea a-fb-text",
    placeholder: L("Sonraki sürümde ne olsun? Bir istek, bir fikir, bir şikâyet…", "What should the next version have? A wish, an idea, a complaint…"),
    maxlength: "2000",
    rows: "4",
  }) as HTMLTextAreaElement;
  const send = h("button", { class: "a-btn primary", text: L("Gönder", "Send") }) as HTMLButtonElement;
  const form = h("div", { class: "a-fb-form" }, starRow, caption, text, h("div", { class: "a-inline" }, send));

  const CAPTIONS: [string, string][] = [
    ["Kaç yıldız?", "How many stars?"],
    ["Of… Gerçekten mi?", "Ouch… really?"],
    ["Daha iyisini yaparız.", "We'll do better."],
    ["Fena değil, ha?", "Not bad, huh?"],
    ["Sevindim!", "Glad you like it!"],
    ["Bayıldın demek!", "You love it!"],
  ];
  function paint() {
    const shown = hover || stars;
    starButtons.forEach((b, i) => {
      b.classList.toggle("on", i < shown);
      b.classList.toggle("picked", i < stars);
    });
    caption.textContent = L(...CAPTIONS[shown]);
    send.disabled = sending || stars === 0;
  }

  /** The mascot's face for a number of stars. */
  function feel(n: number, picked = false) {
    engine.permanentEye = n === 0 || n === 3 ? null : n <= 2 ? "tired" : "happy";
    engine.eyeOverride = engine.permanentEye;
    engine.eyeOverrideUntil = engine.permanentEye ? Number.POSITIVE_INFINITY : 0;
    if (!picked) return;
    if (n === 5) engine.triggerEmote("love", 1.6);
    else if (n === 4) engine.triggerEmote("happy", 1.2);
    else if (n <= 2) { engine.emit("sweat", 1); engine.squash(); }
    else engine.blink();
  }

  send.addEventListener("click", () => {
    if (sending || stars === 0) return;
    sending = true;
    t0 = performance.now() / 1000;
    greeted = false;
    kicked = false;
    sparks = [];
    result = Api.feedback(stars, text.value);
    form.classList.add("folding");
    engine.permanentEye = "happy";
    engine.eyeOverride = "happy";
    engine.eyeOverrideUntil = Number.POSITIVE_INFINITY;
    paint();
  });

  async function finish() {
    const r = result ? await result : { ok: false, error: "bridge" };
    sending = false;
    form.classList.remove("folding");
    if (r.ok) {
      stars = 0;
      text.value = "";
      toast(L("Gönderildi, eline sağlık!", "Sent, thank you!"));
    } else {
      toast(L(`Gönderilemedi (${r.error}). Yazdıkların duruyor, sonra tekrar dene.`, `Couldn't send (${r.error}). Your text is still here; try again later.`));
    }
    feel(stars);
    paint();
  }

  // ── The stage ────────────────────────────────────────────────────────────
  const starsBg = Array.from({ length: 70 }, () => ({ x: Math.random(), y: Math.random() * 0.85, r: 0.4 + Math.random() * 1.2, p: Math.random() * 6 }));
  const blades = Array.from({ length: 120 }, (_, i) => ({ x: i / 119 + (Math.random() - 0.5) * 0.008, h: 8 + Math.random() * 14, lean: (Math.random() - 0.5) * 0.5, tone: Math.random() }));

  function frame(nowMs: number) {
    if (!stage.isConnected) { running = false; return; }
    requestAnimationFrame(frame);
    if (document.hidden) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const W = Math.max(320, stage.clientWidth);
    if (stage.width !== Math.round(W * dpr)) {
      stage.width = Math.round(W * dpr);
      stage.height = Math.round(STAGE_H * dpr);
    }
    const x = stage.getContext("2d");
    if (!x) return;
    x.setTransform(dpr, 0, 0, dpr, 0, 0);
    x.clearRect(0, 0, W, STAGE_H);
    const now = nowMs / 1000;
    const t = sending ? now - t0 : -1;
    try {
      draw(x, W, now, t);
    } catch (err) {
      // A broken frame must not end the film halfway: the form comes back.
      console.error("feedback stage", err);
      if (sending) t0 = now - SEND_S - 1;
    }
    if (sending && t > SEND_S && !finishing) {
      finishing = true;
      void finish().finally(() => { finishing = false; });
    }
  }
  let running = false;
  let finishing = false;
  const startLoop = () => {
    if (running) return;
    running = true;
    requestAnimationFrame(frame);
  };

  function draw(x: CanvasRenderingContext2D, W: number, now: number, t: number) {
    const ground = STAGE_H - 30;
    const home = W * 0.28;
    const letterX = W * 0.62;

    // Space: the sky turns night while the letter flies.
    const night = t < 0 ? 0 : Math.min(easeInOut(span(t, 1.95, 2.6)), 1 - easeInOut(span(t, 4.7, 5.5)));
    if (night > 0.001) {
      x.save();
      x.globalAlpha = night;
      const sky = x.createLinearGradient(0, 0, 0, STAGE_H);
      sky.addColorStop(0, "#05061a");
      sky.addColorStop(0.7, "#141a4a");
      sky.addColorStop(1, "#2a2f6e");
      x.fillStyle = sky;
      roundRect(x, 0, 0, W, STAGE_H, 14);
      x.fill();
      for (const s of starsBg) {
        x.globalAlpha = night * (0.45 + 0.55 * Math.abs(Math.sin(now * 1.6 + s.p)));
        x.fillStyle = "#fff";
        x.beginPath();
        x.arc(s.x * W, s.y * STAGE_H, s.r, 0, Math.PI * 2);
        x.fill();
      }
      x.restore();
    }

    // Grass grows along the floor, then goes again.
    const grass = t < 0 ? 0 : Math.min(back(span(t, 0.3, 0.95)), 1 - easeInOut(span(t, 5.0, 5.6)));
    if (grass > 0.001) {
      x.save();
      x.fillStyle = "#1f8f4a";
      x.globalAlpha = clamp01(grass);
      roundRect(x, 6, ground, W - 12, 8 * clamp01(grass), 4);
      x.fill();
      x.lineCap = "round";
      for (const b of blades) {
        const bx = 6 + b.x * (W - 12);
        const sway = Math.sin(now * 2.2 + b.x * 12) * 2;
        x.strokeStyle = b.tone > 0.5 ? "#2fb457" : "#48d17a";
        x.lineWidth = 2;
        x.beginPath();
        x.moveTo(bx, ground + 2);
        x.quadraticCurveTo(bx + b.lean * 6, ground - b.h * grass * 0.6, bx + b.lean * 10 + sway, ground - b.h * grass);
        x.stroke();
      }
      x.restore();
    }

    // Where Kai is and how it moves.
    let kx = home;
    let lift = 0;
    let tilt = 0;
    let stride = 0;
    let kick = 0;
    if (t >= 0) {
      const run = easeInOut(span(t, 1.0, 1.9));
      const backHome = easeInOut(span(t, 4.75, 5.55));
      kx = lerp(lerp(home, letterX - 58, run), home, backHome);
      const moving = (t > 1.0 && t < 1.9) || (t > 4.75 && t < 5.55);
      if (moving) {
        const fast = t < 2;
        stride = Math.sin(now * (fast ? 24 : 15));
        lift = Math.abs(stride) * (fast ? 9 : 4);
        tilt = (fast ? 0.16 : -0.08) + stride * 0.04;
      }
      // The wind-up and the kick.
      kick = Math.sin(Math.PI * span(t, 1.88, 2.18));
      if (kick > 0) tilt = -0.18 * kick;
      if (t > 2.0 && !kicked) { kicked = true; engine.squash(); }
      if (t > 3.65 && !greeted) { greeted = true; engine.greet(); }
      engine.lookX = t < 2.4 ? 0.85 : t < 3.6 ? 0.6 : t < 4.75 ? 0 : -0.7;
      engine.lookY = t > 2.1 && t < 3.6 ? 0.7 : 0;
    } else {
      // Idle: the face follows the stars. One or two: it slumps, looks down and
      // cries now and then; four: a happy hop; five: hearts all the time.
      const shown = hover || stars;
      engine.lookY = shown && shown <= 2 ? -0.75 : 0;
      engine.lookX = shown ? 0.2 : Math.sin(now * 0.5) * 0.3;
      droop += (((shown && shown <= 2) ? (shown === 1 ? 1 : 0.6) : 0) - droop) * 0.08;
      if (now > nextMood && shown) {
        if (shown <= 2) { engine.emit("sweat", 1); nextMood = now + (shown === 1 ? 1.1 : 1.8); }
        else if (shown === 5) { engine.emit("heart", 2); nextMood = now + 0.9; }
        else if (shown === 4) { engine.squash(); nextMood = now + 2.2; }
        else nextMood = now + 1;
      }
    }

    // The letter: the form folding into an envelope, then the flight.
    if (t >= 0) drawLetter(x, W, t, now, letterX, ground);

    // Kai, with its boots on.
    const boots = t < 0 ? 0 : Math.min(back(span(t, 0.45, 0.8)), 1 - easeInOut(span(t, 5.35, 5.7)));
    // With boots on it stands on them, a clear gap above the studs, not sunk into them.
    const bootH = 32 * clamp01(boots);
    const top = ground - BOT * 0.8 - bootH - lift;
    x.save();
    x.translate(kx, top + BOT * 0.8);
    x.rotate(tilt + droop * 0.06);
    // Slumped: shorter and wider, sitting lower.
    x.scale(1 + droop * 0.06, 1 - droop * 0.1);
    x.translate(-BOT / 2, -BOT * 0.8);
    engine.update(1 / 60);
    engine.draw(x, BOT, BOT);
    x.restore();
    if (boots > 0.01) drawBoots(x, kx, ground - lift, boots, stride, kick);
  }

  function drawLetter(x: CanvasRenderingContext2D, W: number, t: number, now: number, letterX: number, ground: number) {
    const fold = easeInOut(span(t, 0, 0.6));
    const flap = easeOut(span(t, 0.4, 0.75));
    const fly = span(t, 2.0, 3.55);
    // From the form's size to a letter on the grass.
    let w = lerp(W * 0.7, 64, fold);
    let hgt = lerp(150, 42, fold);
    let cx = lerp(W / 2, letterX, fold);
    let cy = lerp(STAGE_H + 40, ground - 21, fold);
    let rot = 0;
    let alpha = clamp01(t / 0.12);
    if (fly > 0) {
      const p = easeOut(fly);
      cx = lerp(letterX, W * 0.9, p) + Math.sin(p * Math.PI) * -W * 0.05;
      cy = lerp(ground - 21, 18, p) - Math.sin(p * Math.PI) * 40;
      rot = p * Math.PI * 3.2;
      const s = lerp(1, 0.18, p);
      w *= s;
      hgt *= s;
      if (Math.random() < 0.7) sparks.push({ x: cx, y: cy, born: now });
      alpha = 1 - span(t, 3.35, 3.55);
    }
    // The trail it leaves in space.
    sparks = sparks.filter((s) => now - s.born < 0.7);
    for (const s of sparks) {
      const a = 1 - (now - s.born) / 0.7;
      x.fillStyle = `rgba(255,214,102,${a * 0.9})`;
      x.beginPath();
      x.arc(s.x + (Math.random() - 0.5) * 3, s.y + (Math.random() - 0.5) * 3, 2.2 * a + 0.4, 0, Math.PI * 2);
      x.fill();
    }
    // Gone among the stars: one twinkle.
    const twinkle = span(t, 3.45, 4.1);
    if (twinkle > 0 && twinkle < 1) {
      const a = Math.sin(twinkle * Math.PI);
      const tx = W * 0.9, ty = 18;
      x.save();
      x.translate(tx, ty);
      x.rotate(twinkle * 1.5);
      x.fillStyle = `rgba(255,240,180,${a})`;
      for (let i = 0; i < 4; i++) {
        x.rotate(Math.PI / 2);
        x.beginPath();
        x.moveTo(0, -18 * a);
        x.lineTo(3, 0);
        x.lineTo(-3, 0);
        x.closePath();
        x.fill();
      }
      x.restore();
    }
    if (alpha <= 0.01) return;

    x.save();
    x.globalAlpha = alpha;
    x.translate(cx, cy);
    x.rotate(rot);
    // Paper.
    x.fillStyle = "#f6efe0";
    x.strokeStyle = "#cdbf9f";
    x.lineWidth = 1.2;
    roundRect(x, -w / 2, -hgt / 2, w, hgt, 4);
    x.fill();
    x.stroke();
    // The writing on it, fading as it folds.
    if (fold < 1) {
      x.globalAlpha = alpha * (1 - fold);
      x.fillStyle = "#b7a98a";
      for (let i = 0; i < 4; i++) x.fillRect(-w / 2 + 14, -hgt / 2 + 18 + i * 22, (w - 28) * (i === 3 ? 0.5 : 1), 5);
      x.globalAlpha = alpha;
    }
    // Envelope lines and the flap closing over it.
    if (fold > 0.5) {
      const e = (fold - 0.5) * 2;
      x.globalAlpha = alpha * e;
      x.beginPath();
      x.moveTo(-w / 2, hgt / 2);
      x.lineTo(0, 0);
      x.lineTo(w / 2, hgt / 2);
      x.stroke();
      x.fillStyle = "#efe4cc";
      x.beginPath();
      x.moveTo(-w / 2, -hgt / 2);
      x.lineTo(0, -hgt / 2 + hgt * 0.62 * flap);
      x.lineTo(w / 2, -hgt / 2);
      x.closePath();
      x.fill();
      x.stroke();
      // A stamp with the stars given.
      x.fillStyle = "#e5484d";
      roundRect(x, w / 2 - w * 0.3, -hgt / 2 + hgt * 0.12, w * 0.22, hgt * 0.3, 2);
      x.fill();
      x.fillStyle = "#ffd666";
      x.font = `${Math.max(6, hgt * 0.2)}px sans-serif`;
      x.textAlign = "center";
      x.textBaseline = "middle";
      x.fillText("★", w / 2 - w * 0.19, -hgt / 2 + hgt * 0.27);
    }
    x.restore();
  }

  /** Football boots with studs: they pop on, run, and one of them kicks. */
  function drawBoots(x: CanvasRenderingContext2D, kx: number, floor: number, s: number, stride: number, kick: number) {
    for (const side of [-1, 1]) {
      const swing = side === 1 ? kick : 0;
      const step = side === 1 ? Math.max(0, stride) : Math.max(0, -stride);
      x.save();
      x.translate(kx + side * BOT * 0.16 + swing * 22, floor - step * 6 - swing * 10);
      x.rotate(-swing * 0.6);
      x.scale(s * 1.45, s * 1.45);
      // The boot: bright red, so it shows on the grass.
      x.fillStyle = "#ff4d5a";
      x.beginPath();
      x.moveTo(-11, -12);
      x.lineTo(4, -12);
      x.quadraticCurveTo(14, -8, 15, -3);
      x.lineTo(15, 0);
      x.lineTo(-11, 0);
      x.closePath();
      x.fill();
      // The sole, its stripe and laces.
      x.fillStyle = "#1b1d24";
      x.fillRect(-11, -2.5, 26, 2.5);
      x.strokeStyle = "#ffffff";
      x.lineWidth = 2;
      x.beginPath();
      x.moveTo(-6, -11);
      x.lineTo(-1, -2);
      x.stroke();
      x.strokeStyle = "#ffe3e5";
      x.lineWidth = 1;
      for (let i = 0; i < 3; i++) {
        x.beginPath();
        x.moveTo(2 + i * 3, -11);
        x.lineTo(4 + i * 3, -7);
        x.stroke();
      }
      // The studs.
      x.fillStyle = "#c9ced8";
      for (const sx of [-8, -2, 5, 11]) x.fillRect(sx - 1.5, 0, 3, 3);
      x.restore();
    }
  }

  // ── The developer's inbox: only on the Kai that holds the inbox key ─────
  const inboxList = h("div", { class: "a-fb-inbox" });
  const inboxNote = h("p", { class: "a-muted" });
  const check = h("button", { class: "a-btn ghost", text: L("Şimdi kontrol et", "Check now") }) as HTMLButtonElement;
  const clearAll = h("button", { class: "a-btn danger", text: L("Hepsini sil", "Delete all") }) as HTMLButtonElement;
  const inboxCard = card(L("Gelen kutusu", "Inbox"), inboxNote, inboxList, h("div", { class: "a-inline" }, check, clearAll));
  inboxCard.style.display = "none";
  async function loadInbox(fetch: boolean, given?: Awaited<ReturnType<typeof Api.feedbackInbox>>) {
    check.disabled = true;
    const r = given ?? await Api.feedbackInbox(fetch);
    check.disabled = false;
    clearAll.style.display = r.items.length ? "" : "none";
    inboxCard.style.display = r.enabled ? "" : "none";
    if (!r.enabled) return;
    const stars = r.items.filter((i) => !i.crash).map((i) => i.stars);
    const crashes = r.items.filter((i) => i.crash).length;
    const avg = stars.length ? (stars.reduce((a, b) => a + b, 0) / stars.length).toFixed(1) : "–";
    inboxNote.textContent = r.error === "nokey"
      ? L("Bu Kai'de sunucu anahtarı yok, yeni değerlendirmeler buraya inemiyor.", "This Kai has no server key, so new ratings can't come in here.")
      : r.error
      ? L(`Sunucuya ulaşılamadı (${r.error}).`, `Couldn't reach the server (${r.error}).`)
      : r.items.length
        ? L(`${stars.length} değerlendirme · ortalama ${avg}★${crashes ? ` · ${crashes} çökme raporu` : ""}. Hepsi Not alıcı'da da duruyor.`,
          `${stars.length} ratings · average ${avg}★${crashes ? ` · ${crashes} crash reports` : ""}. They are in the Notetaker too.`)
        : L("Henüz değerlendirme gelmedi. Kai 10 dakikada bir kendisi de bakıyor.", "No ratings yet. Kai also looks every 10 minutes by itself.");
    inboxList.replaceChildren(...r.items.slice(0, 50).map((i) => h("div", { class: "a-fb-item" },
      h("div", { class: "a-fb-item-head" },
        i.crash
          ? h("span", { class: "a-fb-item-crash", text: L("Çökme raporu", "Crash report") })
          : h("span", { class: "a-fb-item-stars", text: "★".repeat(i.stars) + "☆".repeat(5 - i.stars) }),
        h("span", { class: "a-muted", text: `${new Date(i.at * 1000).toLocaleString(L("tr-TR", "en-GB"), { dateStyle: "short", timeStyle: "short" })} · ${i.meta}` }),
        deleteButton(i.id)),
      h("div", { class: "a-fb-item-text", text: i.text }))));
  }
  check.addEventListener("click", async () => { await loadInbox(true); toast(L("Gelen kutusu güncel", "Inbox up to date")); });

  /** Deleting goes from this Kai only: the server keeps nothing once a rating is received. */
  function deleteButton(id: string): HTMLElement {
    const b = h("button", { class: "a-fb-item-del", title: L("Sil", "Delete"), text: L("Sil", "Delete") });
    b.addEventListener("click", async () => {
      await loadInbox(false, await Api.feedbackDelete(id));
    });
    return b;
  }
  // "Delete all" asks once more on the button itself before it goes.
  let armed = 0;
  clearAll.addEventListener("click", async () => {
    if (Date.now() - armed > 3000) {
      armed = Date.now();
      clearAll.textContent = L("Emin misin? Tekrar bas", "Sure? Press again");
      window.setTimeout(() => { if (Date.now() - armed >= 3000) clearAll.textContent = L("Hepsini sil", "Delete all"); }, 3100);
      return;
    }
    armed = 0;
    clearAll.textContent = L("Hepsini sil", "Delete all");
    await loadInbox(false, await Api.feedbackDelete("all"));
    toast(L("Hepsi silindi", "All deleted"));
  });

  feel(0);
  paint();
  requestAnimationFrame(startLoop);
  const el = h(
    "div",
    { class: "a-page" },
    card(
      L("Bu sürüme kaç yıldız?", "How many stars for this version?"),
      stage,
      form,
      h("p", { class: "a-muted", text: L(
        "Yıldızların ve yazdığın, sürüm numarasıyla birlikte Kai'nin geliştiricisine gider. Adın, e-postan ya da bilgisayarınla ilgili hiçbir şey gönderilmez.",
        "Your stars and what you write go to Kai's developer, with the version number. Nothing about your name, email or computer is sent.") }),
    ),
    inboxCard,
  );
  Object.assign(el, { __engine: engine, __start: startLoop, __inbox: loadInbox });
  void loadInbox(false);
  return el;
}

function roundRect(x: CanvasRenderingContext2D, X: number, Y: number, w: number, h: number, r: number) {
  x.beginPath();
  x.moveTo(X + r, Y);
  x.arcTo(X + w, Y, X + w, Y + h, r);
  x.arcTo(X + w, Y + h, X, Y + h, r);
  x.arcTo(X, Y + h, X, Y, r);
  x.arcTo(X, Y, X + w, Y, r);
  x.closePath();
}
