// How the computer feels, as the mascot shows it — after coucou's MochiMood.swift.
// The host reads it (vitals.py); the engine eases towards it and plays it:
// sweat drops and panicked hops under full processor load, a red flush and heat
// waves when warm, puffed up when memory is short, heavy eyelids on a low
// battery and asleep when it is nearly empty.

export interface Mood {
  /** The processor is at full load. 0…1 */
  busy: number;
  /** The computer is warm. 0…1 */
  hot: number;
  /** Memory is short. 0…1 */
  full: number;
  /** The battery is low. 0…1 */
  tired: number;
  /** The battery is nearly empty. */
  asleep: boolean;
}

export const CALM: Mood = { busy: 0, hot: 0, full: 0, tired: 0, asleep: false };

/** A drop of sweat thrown from the side: it rises, then falls in an arc. In R, from the centre. */
export interface Drop {
  x: number; y: number; vx: number; vy: number;
  born: number; size: number; stretch: number; tint: number; alpha: number; wobble: number;
}

/** One of the stressed hops, from side to side. */
export interface Hop {
  from: number; to: number; start: number; duration: number; height: number; rest: number; landed: boolean;
}

export const DROP_GRAVITY = 6.0;

const rand = (a: number, b: number) => a + Math.random() * (b - a);

export function newDrop(now: number, ox: number, oy: number): Drop {
  const side = Math.random() < 0.5 ? 1 : -1;
  // Now and then a small round droplet, mostly a full drop.
  const small = Math.random() < 0.3;
  return {
    x: side * rand(0.92, 1.05) + ox, y: rand(-0.5, -0.25) + oy,
    vx: side * rand(0.5, 1.0), vy: -rand(1.5, 2.4), born: now,
    size: small ? rand(0.09, 0.13) : rand(0.15, 0.26),
    stretch: small ? rand(0.75, 0.95) : rand(1.0, 1.55),
    tint: Math.random(), alpha: rand(0.7, 1), wobble: rand(0, Math.PI * 2),
  };
}

/** Sweat drops and heat waves, in canvas space around the body's centre. */
export function drawMoodExtras(
  x: CanvasRenderingContext2D, drops: Drop[], hot: number, now: number,
  R: number, ry: number, cx: number, cy: number,
) {
  for (const d of drops) {
    const a = now - d.born;
    if (a < 0) continue;
    const px = d.x + d.vx * a;
    const py = d.y + d.vy * a + (DROP_GRAVITY * a * a) / 2;
    const vy = d.vy + DROP_GRAVITY * a;
    const s = R * d.size;
    const wob = 1 + Math.sin(a * 22 + d.wobble) * 0.08;
    const long = d.stretch * wob;
    x.save();
    x.globalAlpha = d.alpha * Math.min(1, a / 0.06) * Math.min(1, Math.max(0, (1.05 - py) / 0.25));
    x.translate(cx + px * R, cy + py * R);
    x.rotate(Math.atan2(vy, d.vx) - Math.PI / 2);
    const tear = new Path2D();
    tear.moveTo(0, -s * 1.15 * long);
    tear.quadraticCurveTo((s * 0.9) / wob, s * 0.2, 0, s * 0.7);
    tear.quadraticCurveTo((-s * 0.9) / wob, s * 0.2, 0, -s * 1.15 * long);
    // From a pale sky blue to a deeper blue, lighter at the top.
    const g = x.createLinearGradient(0, -s * long, 0, s * 0.7);
    g.addColorStop(0, `rgb(${Math.round(255 * (0.72 - 0.2 * d.tint))},${Math.round(255 * (0.88 - 0.12 * d.tint))},255)`);
    g.addColorStop(1, `rgb(${Math.round(255 * (0.36 - 0.12 * d.tint))},${Math.round(255 * (0.68 - 0.14 * d.tint))},250)`);
    x.fillStyle = g;
    x.fill(tear);
    x.fillStyle = `rgba(255,255,255,${0.4 + 0.35 * d.tint})`;
    x.beginPath();
    x.ellipse(-s * 0.25, s * 0.06 * long, s * 0.11, s * 0.16 * long, 0, 0, Math.PI * 2);
    x.fill();
    x.restore();
  }

  // Heat waves: three wavy lines rising above the head.
  if (hot > 0.5) {
    const k = (hot - 0.5) * 2;
    x.save();
    x.strokeStyle = "rgb(255,140,77)";
    x.lineWidth = Math.max(1, R * 0.07);
    x.lineCap = "round";
    for (let i = 0; i < 3; i++) {
      const x0 = cx + (i - 1) * R * 0.42;
      const phase = now * 3 + i * 1.7;
      const rise = (now * 0.6 + i * 0.33) % 1;
      const top = cy - ry * 1.18 - R * 0.55 * rise;
      const len = R * 0.5;
      x.globalAlpha = k * Math.sin(rise * Math.PI);
      x.beginPath();
      for (let s = 0; s <= 12; s++) {
        const f = s / 12;
        const px = x0 + Math.sin(phase + f * 6) * R * 0.07;
        const py = top - f * len;
        if (s === 0) x.moveTo(px, py);
        else x.lineTo(px, py);
      }
      x.stroke();
    }
    x.restore();
  }
}
