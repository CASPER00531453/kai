// The day's summary, once an evening at the time set in Kai's settings
// (daily.py on the host). Kai puts its glasses on and reads the report it holds
// while the lines come up on the right, one after the other.

import { h, clear } from "./dom";
import { washRGBA } from "../core/layout";
import { prefs, turkish } from "../core/prefs";
import { BotEngine } from "../mochi/engine";
import { parseMascot } from "../mochi/mascots";
import type { ViewHost } from "./views";

export interface DailyReport {
  title: string;
  lines: { icon: string; text: string }[];
}

/** What the next opening of the view shows; set by main.ts from the host's poll. */
export const Summary = { report: null as DailyReport | null, shownAt: 0 };

const L = (tr: string, en: string) => (turkish() ? tr : en);
const STAGE = 190;

export function buildSummary(back: () => void): ViewHost {
  const engine = new BotEngine();
  engine.setOutfit("roundGlasses", false);
  const stage = h("canvas", { class: "summary-stage" }) as HTMLCanvasElement;
  const title = h("div", { class: "summary-title" });
  const lines = h("div", { class: "summary-lines" });
  const done = h("button", { class: "btn primary", onclick: back }, h("span"));
  const right = h("div", { class: "summary-right" }, title, lines, h("div", { class: "actions" }, done));
  const card = h("div", { class: "card wash summary-card" }, stage, right);
  card.style.setProperty("--wash", washRGBA("indigo"));
  const el = h("div", { class: "view" }, card);

  let key = "";
  let last = 0;
  let nextBlink = 0;
  let nextNod = 0;

  /** The sheet in Kai's hands, with its own lines of text, turned now and then. */
  function paper(x: CanvasRenderingContext2D, t: number) {
    const page = Math.floor(t / 4.5);
    // A page turned: the sheet lifts and comes back.
    const flip = Math.max(0, 1 - Math.abs((t % 4.5) - 4.3) / 0.2);
    const bob = Math.sin(t * 1.7) * 1.5;
    x.save();
    x.translate(STAGE / 2, STAGE * 0.7 + bob - flip * 6);
    x.rotate(-0.08 + Math.sin(t * 0.9) * 0.03);
    const w = 66;
    const hh = 50;
    x.shadowColor = "rgba(0,0,0,0.35)";
    x.shadowBlur = 6;
    x.fillStyle = "#f7f4ea";
    x.beginPath();
    x.roundRect(-w / 2, -hh / 2, w, hh, 3);
    x.fill();
    x.shadowBlur = 0;
    // A folded corner.
    x.fillStyle = "#ddd6c2";
    x.beginPath();
    x.moveTo(w / 2 - 10, -hh / 2);
    x.lineTo(w / 2, -hh / 2 + 10);
    x.lineTo(w / 2 - 10, -hh / 2 + 10);
    x.fill();
    // Lines of text, a bar chart on every other page.
    x.fillStyle = "rgba(60,70,95,0.55)";
    for (let i = 0; i < 5; i++) {
      const len = 0.45 + ((page * 7 + i * 13) % 10) / 22;
      x.fillRect(-w / 2 + 7, -hh / 2 + 8 + i * 8, (w - 18) * len, 2.4);
    }
    if (page % 2) {
      x.fillStyle = "#4DB5FF";
      [10, 16, 8].forEach((bh, i) => x.fillRect(w / 2 - 22 + i * 6, hh / 2 - 6 - bh, 4, bh));
    }
    // The hands holding it.
    x.fillStyle = "#e9eef7";
    for (const side of [-1, 1]) {
      x.beginPath();
      x.ellipse(side * (w / 2 - 2), 6, 6.5, 5.5, 0, 0, Math.PI * 2);
      x.fill();
    }
    x.restore();
  }

  return {
    el,
    sync() {
      title.textContent = Summary.report?.title || L("Günün özeti", "Your day");
      (done.firstChild as HTMLElement).textContent = L("Tamam", "Done");
      const report = Summary.report;
      const next = JSON.stringify(report?.lines ?? []);
      if (next === key) return;
      key = next;
      clear(lines);
      // One after the other, as if Kai read them out of the sheet.
      (report?.lines ?? []).slice(0, 6).forEach((line, i) => {
        const row = h("div", { class: "summary-line" },
          h("span", { class: "summary-icon", text: line.icon }),
          h("span", { text: line.text }));
        row.style.animationDelay = `${0.5 + i * 0.55}s`;
        lines.append(row);
      });
    },
    tick(nowMs: number) {
      const dt = last ? Math.min(0.05, (nowMs - last) / 1000) : 1 / 60;
      last = nowMs;
      const t = nowMs / 1000;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      if (stage.width !== Math.round(STAGE * dpr)) {
        stage.width = Math.round(STAGE * dpr);
        stage.height = Math.round(STAGE * dpr);
      }
      const x = stage.getContext("2d");
      if (!x) return;
      engine.mascot = parseMascot(prefs()?.mascot);
      // Reading: the eyes run along a line, jump back, and look down at the sheet.
      const phase = (t * 0.55) % 1;
      engine.lookX = phase < 0.85 ? -0.55 + (phase / 0.85) * 1.1 : 0.55 - ((phase - 0.85) / 0.15) * 1.1;
      engine.lookY = 0.55;
      if (t > nextBlink) {
        nextBlink = t + 2.5 + Math.random() * 2.5;
        engine.blink();
      }
      // Now and then a nod, as if something in the report pleased it.
      if (t > nextNod) {
        nextNod = t + 5 + Math.random() * 4;
        if (nextNod > 0 && Math.random() < 0.6) engine.squash();
      }
      engine.update(dt);
      x.setTransform(dpr, 0, 0, dpr, 0, 0);
      x.clearRect(0, 0, STAGE, STAGE);
      x.save();
      x.translate(STAGE * 0.11, 0);
      engine.draw(x, STAGE * 0.78, STAGE * 0.78);
      x.restore();
      paper(x, t);
    },
  };
}
