// The living parts of the Kai window: a band of Kai's mascots walking along
// the top of each page, and specks of light that drift away from the pointer.

import { BotEngine, hexToRGB } from "../mochi/engine";
import { PICKABLE, type Mascot } from "../mochi/mascots";

interface Walker {
  engine: BotEngine;
  x: number;
  dir: number;
  speed: number;
  hop: number; // 0…1 progress of a hop, or 0
  pause: number; // seconds left standing still
  next: number; // seconds until it does something
  size: number;
}

const rand = (a: number, b: number) => a + Math.random() * (b - a);

export class Band {
  readonly el: HTMLCanvasElement;
  private walkers: Walker[] = [];
  private color = "#1a7fd4";
  private main: Mascot = "ghost";

  constructor() {
    this.el = document.createElement("canvas");
    this.el.className = "a-band";
    this.el.addEventListener("click", (e) => this.poke(e));
  }

  /** The page's colour, and the user's own mascot first in the line. */
  setup(color: string, main: Mascot) {
    this.color = color;
    this.main = main;
    const others = PICKABLE.filter((m) => m !== main);
    const kinds: Mascot[] = [main, ...others.sort(() => Math.random() - 0.5).slice(0, 4)];
    const w = this.el.clientWidth || 800;
    this.walkers = kinds.map((kind, i) => {
      const engine = new BotEngine();
      engine.mascot = kind;
      // The user's mascot keeps its own colour; the others wear the page's.
      engine.bodyColor = i === 0 ? null : hexToRGB(shade(color, i));
      return {
        engine,
        x: ((i + 0.5) / kinds.length) * w,
        dir: Math.random() < 0.5 ? -1 : 1,
        speed: rand(16, 30),
        hop: 0,
        pause: 0,
        next: rand(1, 4),
        size: i === 0 ? 52 : rand(38, 46),
      };
    });
  }

  private poke(e: MouseEvent) {
    const rect = this.el.getBoundingClientRect();
    const x = e.clientX - rect.left;
    let best: Walker | null = null;
    for (const w of this.walkers) if (Math.abs(w.x - x) < w.size * 0.6 && (!best || Math.abs(w.x - x) < Math.abs(best.x - x))) best = w;
    if (!best) return;
    best.hop = 0.001;
    best.engine.squash();
    best.engine.emit(Math.random() < 0.5 ? "heart" : "star", 3);
    best.pause = 0.8;
  }

  step(dt: number) {
    const canvas = this.el;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const W = canvas.clientWidth;
    const H = canvas.clientHeight;
    if (!W || !H) return;
    if (canvas.width !== Math.round(W * dpr)) {
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    for (const w of this.walkers) {
      w.next -= dt;
      if (w.next <= 0) {
        const roll = Math.random();
        if (roll < 0.25) w.dir *= -1;
        else if (roll < 0.5) w.hop = 0.001;
        else if (roll < 0.65) w.engine.blink();
        else if (roll < 0.8) w.pause = rand(0.8, 2.2);
        w.next = rand(1.5, 4.5);
      }
      if (w.pause > 0) w.pause -= dt;
      else w.x += w.dir * w.speed * dt;
      const edge = w.size * 0.6;
      if (w.x < edge) { w.x = edge; w.dir = 1; }
      if (w.x > W - edge) { w.x = W - edge; w.dir = -1; }
      w.engine.tgYaw = w.pause > 0 ? 0 : w.dir * 0.45;
      let lift = 0;
      if (w.hop > 0) {
        w.hop += dt * 2.6;
        lift = Math.sin(Math.min(1, w.hop) * Math.PI) * w.size * 0.5;
        if (w.hop >= 1) w.hop = 0;
      }
      const walkBob = w.pause > 0 ? 0 : Math.abs(Math.sin(performance.now() / 160 + w.x)) * 2;
      w.engine.update(dt);
      const box = w.size * 1.7;
      ctx.save();
      ctx.translate(w.x - box / 2, H - box - 2 - lift - walkBob);
      w.engine.draw(ctx, box, box);
      ctx.restore();
    }
    void this.color;
    void this.main;
  }
}

/** The page colour, a little lighter or darker per walker. */
function shade(hex: string, i: number): string {
  const n = parseInt(hex.slice(1), 16);
  const k = [0, 0.18, -0.12, 0.3, -0.22][i % 5];
  const ch = (v: number) => Math.round(k >= 0 ? v + (255 - v) * k : v * (1 + k));
  const r = ch((n >> 16) & 255), g = ch((n >> 8) & 255), b = ch(n & 255);
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`;
}

/** Specks of light behind everything; they lean away from the pointer. */
export class Particles {
  private dots: { x: number; y: number; vx: number; vy: number; r: number; a: number }[] = [];
  private px = -999;
  private py = -999;
  color = "#1a7fd4";

  constructor(private canvas: HTMLCanvasElement) {
    window.addEventListener("pointermove", (e) => { this.px = e.clientX; this.py = e.clientY; });
    window.addEventListener("pointerleave", () => { this.px = this.py = -999; });
    for (let i = 0; i < 70; i++) {
      this.dots.push({ x: Math.random(), y: Math.random(), vx: rand(-0.004, 0.004), vy: rand(-0.008, -0.002), r: rand(0.6, 1.8), a: rand(0.15, 0.55) });
    }
  }

  step(dt: number) {
    const c = this.canvas;
    // Specks of light need no sharpness: drawn at one pixel per CSS pixel, a quarter of the work on a scaled screen.
    const dpr = 1;
    const W = window.innerWidth;
    const H = window.innerHeight;
    if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) {
      c.width = Math.round(W * dpr);
      c.height = Math.round(H * dpr);
    }
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = this.color;
    for (const d of this.dots) {
      const sx = d.x * W;
      const sy = d.y * H;
      const dx = sx - this.px;
      const dy = sy - this.py;
      const dist = Math.hypot(dx, dy);
      if (dist < 140 && dist > 0.1) {
        const push = (1 - dist / 140) * 0.06;
        d.vx += (dx / dist) * push * dt;
        d.vy += (dy / dist) * push * dt;
      }
      d.vx *= 1 - 0.9 * dt;
      d.vy = d.vy * (1 - 0.9 * dt) - 0.004 * dt;
      d.x += d.vx * dt;
      d.y += d.vy * dt;
      if (d.y < -0.02) { d.y = 1.02; d.x = Math.random(); }
      if (d.x < -0.02) d.x = 1.02;
      if (d.x > 1.02) d.x = -0.02;
      if (d.y > 1.04) d.y = -0.02;
      ctx.globalAlpha = d.a;
      ctx.beginPath();
      ctx.arc(d.x * W, d.y * H, d.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
}
