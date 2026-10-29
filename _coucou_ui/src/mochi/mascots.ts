// Kai's own mascots. Each one is a silhouette for the bot engine: the engine
// keeps every movement it has (blink, look, squash, hands, emotes) and only the
// body it draws changes. "mochi" is the engine's original body.
//
// Shapes are written on a 100-unit sheet, as in the mascot gallery, with the
// point between the eyes given per mascot. That point lands on the body's
// origin, where the engine draws the eyes; one sheet unit is UNIT × R.

import { turkish } from "../core/prefs";

export const MASCOTS = [
  "ghost", "mochi", "clover", "ears", "drop", "antenna", "cat", "cloud", "star",
  "bunny", "bear", "bean", "hex", "flame", "planet", "sprout",
] as const;
export type Mascot = (typeof MASCOTS)[number];

/**
 * The mascots a user can pick. "mochi" is not one of them: the Mochi character
 * belongs to Coucou's author and is not covered by its MIT license
 * (LICENSE-ASSETS.md upstream), so Kai never shows it as a mascot.
 */
export const PICKABLE: readonly Mascot[] = MASCOTS.filter((m) => m !== "mochi");

export const DEFAULT_MASCOT: Mascot = "ghost";

/** Each name as [Türkçe, English]. */
const NAMES: Record<Mascot, [string, string]> = {
  ghost: ["Hayalet", "Ghost"], mochi: ["Mochi", "Mochi"], clover: ["Yonca", "Clover"], ears: ["Kulaklı", "Ears"],
  drop: ["Damla", "Drop"], antenna: ["Anten", "Antenna"], cat: ["Kedi", "Cat"], cloud: ["Bulut", "Cloud"],
  star: ["Yıldız", "Star"], bunny: ["Tavşan", "Bunny"], bear: ["Ayı", "Bear"], bean: ["Fasulye", "Bean"],
  hex: ["Altıgen", "Hexagon"], flame: ["Kıvılcım", "Spark"], planet: ["Gezegen", "Planet"], sprout: ["Filiz", "Sprout"],
};

export const mascotLabel = (kind: Mascot) => NAMES[kind][turkish() ? 0 : 1];

export function parseMascot(raw: unknown): Mascot {
  return typeof raw === "string" && (PICKABLE as readonly string[]).includes(raw) ? (raw as Mascot) : DEFAULT_MASCOT;
}

type Ctx = CanvasRenderingContext2D;
type Pt = [number, number];

const UNIT = 0.031;
const INK = "rgb(26,20,18)";

/** Where the eyes sit on each mascot's sheet. */
const FACE: Record<Exclude<Mascot, "mochi">, Pt> = {
  ghost: [50, 50], clover: [50, 53], ears: [50, 57], drop: [50, 62], antenna: [50, 58], cat: [50, 58],
  cloud: [50, 62], star: [50, 53], bunny: [50, 62], bear: [50, 50], bean: [54, 50], hex: [50, 52],
  flame: [50, 63], planet: [50, 49], sprout: [50, 62],
};

/** Top and bottom of everything each mascot draws, on its sheet. */
const SPAN: Record<Exclude<Mascot, "mochi">, [number, number]> = {
  ghost: [14, 96], clover: [7, 97], ears: [14, 86], drop: [4, 92], antenna: [0, 86], cat: [9, 86],
  cloud: [13, 86], star: [6, 92], bunny: [-3, 88], bear: [18, 91], bean: [12, 92], hex: [10, 94],
  flame: [2, 92], planet: [21, 85], sprout: [6, 88],
};

/**
 * How a pill's small bot is placed: [scale, shift down]. A pill is only as
 * tall as the original body, so a taller mascot is shrunk to that height and
 * centred in it, ears and all.
 */
export function mascotMiniFit(kind: Mascot, R: number): [number, number] {
  if (kind === "mochi") return [1, 0];
  const [top, bottom] = SPAN[kind];
  const u = R * UNIT;
  const scale = Math.min(0.9, (1.84 * R) / ((bottom - top) * u));
  return [scale, -((top + bottom) / 2 - FACE[kind][1]) * u * scale];
}

// ── Sheet-space builders. Every outline runs clockwise, so parts of one body can overlap. ──

function circle(cx: number, cy: number, r: number): Path2D {
  const p = new Path2D();
  p.arc(cx, cy, r, 0, Math.PI * 2);
  return p;
}

function oval(cx: number, cy: number, rx: number, ry: number): Path2D {
  const p = new Path2D();
  p.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  return p;
}

function box(x: number, y: number, w: number, h: number, r: number): Path2D {
  const p = new Path2D();
  p.moveTo(x + r, y);
  p.arcTo(x + w, y, x + w, y + h, r);
  p.arcTo(x + w, y + h, x, y + h, r);
  p.arcTo(x, y + h, x, y, r);
  p.arcTo(x, y, x + w, y, r);
  p.closePath();
  return p;
}

/** A polygon with its corners rounded. Points go clockwise. */
function rounded(points: Pt[], r: number): Path2D {
  const p = new Path2D();
  const n = points.length;
  const mid = (a: Pt, b: Pt): Pt => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const start = mid(points[n - 1], points[0]);
  p.moveTo(start[0], start[1]);
  for (let i = 0; i < n; i++) {
    const next = points[(i + 1) % n];
    const to = mid(points[i], next);
    p.arcTo(points[i][0], points[i][1], to[0], to[1], r);
  }
  p.closePath();
  return p;
}

function join(...parts: Path2D[]): Path2D {
  const p = new Path2D();
  for (const part of parts) p.addPath(part);
  return p;
}

function star(): Path2D {
  const points: Pt[] = [];
  for (let i = 0; i < 10; i++) {
    const a = -Math.PI / 2 + (i * Math.PI) / 5;
    const r = i % 2 === 0 ? 47 : 29;
    points.push([50 + r * Math.cos(a), 53 + r * Math.sin(a)]);
  }
  return rounded(points, 7);
}

/** The body the eyes are clipped to, and the parts that stand behind it (ears, a stem). */
function sheet(kind: Mascot, seconds: number): { body: Path2D; behind: Path2D[] } | null {
  switch (kind) {
    case "mochi":
      return null;
    case "ghost": {
      // A dome over a hem that ripples: the waves travel along it with time.
      const body = new Path2D();
      const hem = (px: number) => 86 + 5 * Math.sin(((84 - px) / 68) * Math.PI * 4 + seconds * 3.2);
      body.moveTo(16, 52);
      body.ellipse(50, 52, 34, 38, 0, Math.PI, Math.PI * 2);
      for (let px = 84; px >= 16; px -= 4) body.lineTo(px, hem(px));
      body.closePath();
      return { body, behind: [] };
    }
    case "clover":
      return { body: join(circle(50, 30, 23), circle(50, 74, 23), circle(28, 52, 23), circle(72, 52, 23), circle(50, 52, 27)), behind: [] };
    case "ears":
      return { body: box(13, 26, 74, 60, 27), behind: [circle(30, 27, 13), circle(70, 27, 13)] };
    case "drop":
      return { body: new Path2D("M52 4 C50 22 86 38 86 62 A36 30 0 0 1 14 62 C14 40 38 30 44 16 C46 12 49 7 52 4Z"), behind: [] };
    case "antenna":
      return { body: box(14, 28, 72, 58, 28), behind: [box(47.5, 8, 5, 24, 2.5)] };
    case "cat":
      return {
        body: box(12, 28, 76, 58, 28),
        behind: [rounded([[19, 9], [47, 30], [15, 46]], 5), rounded([[81, 9], [85, 46], [53, 30]], 5)],
      };
    case "cloud":
      return { body: join(circle(31, 48, 20), circle(52, 38, 25), circle(73, 50, 18), box(11, 48, 80, 38, 19)), behind: [] };
    case "star":
      return { body: star(), behind: [] };
    case "bunny":
      return { body: box(16, 34, 68, 54, 27), behind: [oval(36, 18, 9, 21), oval(64, 18, 9, 21)] };
    case "bear":
      return { body: circle(50, 55, 36), behind: [circle(24, 30, 12), circle(76, 30, 12)] };
    case "bean":
      return { body: new Path2D("M32 14 C54 6 82 24 84 52 C86 80 62 96 40 90 C22 85 14 68 22 56 C29 45 20 22 32 14Z"), behind: [] };
    case "hex":
      return { body: rounded([[50, 10], [86, 31], [86, 73], [50, 94], [14, 73], [14, 31]], 9), behind: [] };
    case "flame":
      return { body: new Path2D("M50 2 C56 22 84 34 84 62 A34 30 0 0 1 16 62 C16 46 27 40 31 27 C37 36 41 38 44 30 C47 22 46 12 50 2Z"), behind: [] };
    case "planet":
      return { body: circle(50, 53, 32), behind: [] };
    case "sprout":
      return { body: box(16, 32, 68, 56, 28), behind: [box(48, 14, 4, 22, 2)] };
  }
}

const cache = new Map<string, { body: Path2D; behind: Path2D[] } | null>();

/** The mascot's outline in the engine's body space for a body of base unit R; null for Mochi. */
export function mascotShape(kind: Mascot, R: number, seconds = 0): { body: Path2D; behind: Path2D[] } | null {
  if (kind === "mochi") return null;
  // The ghost's outline changes with time; every other one is drawn once per size.
  const moving = kind === "ghost";
  const key = `${kind}:${R.toFixed(2)}`;
  const hit = moving ? undefined : cache.get(key);
  if (hit !== undefined) return hit;
  const drawn = sheet(kind, seconds);
  let out: { body: Path2D; behind: Path2D[] } | null = null;
  if (drawn) {
    const [fx, fy] = FACE[kind];
    const u = R * UNIT;
    const place = (source: Path2D) => {
      const p = new Path2D();
      p.addPath(source, new DOMMatrix([u, 0, 0, u, -fx * u, -fy * u]));
      return p;
    };
    out = { body: place(drawn.body), behind: drawn.behind.map(place) };
  }
  if (moving) return out;
  if (cache.size > 64) cache.clear();
  cache.set(key, out);
  return out;
}

/** The colour of the eyes, when the mascot needs its own (the robot's visor is dark). */
export function mascotInk(kind: Mascot): string | null {
  return kind === "hex" ? "#8fe6ff" : null;
}

/** Runs `draw` on the mascot's sheet, placed on the body. */
function onSheet(x: Ctx, kind: Mascot, R: number, draw: () => void) {
  if (kind === "mochi") return;
  const [fx, fy] = FACE[kind];
  const u = R * UNIT;
  x.save();
  x.transform(u, 0, 0, u, -fx * u, -fy * u);
  draw();
  x.restore();
}

function planetRing(x: Ctx, front: boolean) {
  x.save();
  x.translate(50, 56);
  x.rotate(-0.245);
  x.beginPath();
  // The near half of the ring passes in front of the planet, the far half behind.
  if (front) x.ellipse(0, 0, 49, 12, 0, 0, Math.PI);
  else x.ellipse(0, 0, 49, 12, 0, 0, Math.PI * 2);
  x.strokeStyle = "#bfe8ff";
  x.lineWidth = 5;
  x.lineCap = "round";
  x.stroke();
  x.restore();
}

/** Drawn before anything else of the bot. */
export function drawMascotUnder(x: Ctx, kind: Mascot, R: number) {
  if (kind === "planet") onSheet(x, kind, R, () => planetRing(x, false));
}

/** Drawn on the body, under the eyes. */
export function drawMascotMid(x: Ctx, kind: Mascot, R: number, seconds = 0) {
  onSheet(x, kind, R, () => {
    if (kind === "hex") {
      x.fillStyle = "#0a1622";
      x.fill(box(24, 39, 52, 26, 13));
    } else if (kind === "bear") {
      x.fillStyle = "rgba(255,255,255,0.28)";
      x.fill(oval(50, 68, 14, 10));
      x.fillStyle = INK;
      x.fill(oval(50, 64, 4, 3));
    } else if (kind === "bunny") {
      // The pink of each ear moves with its ear.
      x.fillStyle = "rgba(255,255,255,0.3)";
      [oval(36, 19, 4, 13), oval(64, 19, 4, 13)].forEach((inner, index) => {
        x.save();
        hinged(x, kind, index, seconds);
        x.fill(inner);
        x.restore();
      });
    }
  });
}

/** Drawn over the whole bot. */
export function drawMascotOver(x: Ctx, kind: Mascot, R: number, seconds: number) {
  onSheet(x, kind, R, () => {
    if (kind === "planet") {
      planetRing(x, true);
    } else if (kind === "antenna") {
      hinged(x, kind, 0, seconds);
      // The tip breathes, a little brighter every second and a half.
      x.globalAlpha = 0.72 + 0.28 * Math.sin(seconds * 4.2);
      x.fillStyle = "#d9f4ff";
      x.fill(circle(50, 7, 6.5));
      x.globalAlpha = 1;
    } else if (kind === "sprout") {
      hinged(x, kind, 0, seconds);
      // Two leaves that lean with a slow breeze.
      x.translate(50, 18);
      x.rotate(0.07 * Math.sin(seconds * 2.4));
      x.translate(-50, -18);
      x.fillStyle = "#5ee0a0";
      x.fill(new Path2D("M50 18 C40 3 25 7 23 16 C33 23 44 23 50 18Z"));
      x.fillStyle = "#3fcf8a";
      x.fill(new Path2D("M50 18 C60 3 75 7 77 16 C67 23 56 23 50 18Z"));
    }
  });
}

// ── Movement. Every mascot keeps the engine's moves and adds one of its own. ──

/** An extra pose on top of the engine's: shift, turn and stretch around a point pivotY below the face. */
export interface Motion { dx: number; dy: number; rot: number; sx: number; sy: number; pivotY: number }

const still = (pivotY = 0): Motion => ({ dx: 0, dy: 0, rot: 0, sx: 1, sy: 1, pivotY });

/**
 * The mascot's own idle move at `seconds`, for a body of base unit R. `calm`
 * scales it down (a pill's bot has little room to move in).
 */
export function mascotMotion(kind: Mascot, R: number, seconds: number, calm = 1): Motion | null {
  const t = seconds;
  const foot = R * 0.9;
  const m = still();
  switch (kind) {
    case "ghost": // drifts, never quite still
      m.dy = Math.sin(t * 1.8) * 0.07 * R;
      m.dx = Math.sin(t * 0.9) * 0.05 * R;
      m.rot = Math.sin(t * 0.9) * 0.03;
      break;
    case "cloud":
      m.dy = Math.sin(t * 1.4) * 0.05 * R;
      m.dx = Math.sin(t * 0.7) * 0.07 * R;
      break;
    case "bunny": { // crouch, hop, land
      m.pivotY = foot;
      const p = (t % 2.6) / 2.6;
      if (p < 0.08) {
        const k = Math.sin((p / 0.08) * Math.PI);
        m.sx = 1 + 0.07 * k;
        m.sy = 1 - 0.1 * k;
      } else if (p < 0.34) {
        const k = Math.sin(((p - 0.08) / 0.26) * Math.PI);
        m.dy = -k * 0.36 * R;
        m.sx = 1 - 0.04 * k;
        m.sy = 1 + 0.06 * k;
      } else if (p < 0.42) {
        const k = Math.sin(((p - 0.34) / 0.08) * Math.PI);
        m.sx = 1 + 0.06 * k;
        m.sy = 1 - 0.08 * k;
      }
      break;
    }
    case "flame": // flickers like a small fire
      m.pivotY = foot;
      m.sx = 1 + 0.03 * Math.sin(t * 9.5);
      m.sy = 1 - 0.035 * Math.sin(t * 9.5) + 0.02 * Math.sin(t * 4.3);
      m.rot = 0.035 * Math.sin(t * 5.1);
      break;
    case "star": // twinkles
      m.rot = 0.14 * Math.sin(t * 1.4);
      m.sx = m.sy = 1 + 0.025 * Math.sin(t * 2.8);
      break;
    case "planet":
      m.rot = 0.09 * Math.sin(t * 1.1);
      break;
    case "bean":
      m.pivotY = foot;
      m.rot = 0.1 * Math.sin(t * 1.9);
      break;
    case "drop": // wobbles like water
      m.pivotY = foot;
      m.rot = 0.07 * Math.sin(t * 1.6);
      m.sy = 1 + 0.025 * Math.sin(t * 3.2);
      m.sx = 1 - 0.02 * Math.sin(t * 3.2);
      break;
    case "clover":
      m.rot = 0.07 * Math.sin(t * 1.2);
      break;
    case "hex": // hovers
      m.dy = Math.sin(t * 2.6) * 0.03 * R;
      break;
    default:
      return null;
  }
  m.dx *= calm;
  m.dy *= calm;
  m.rot *= calm;
  m.sx = 1 + (m.sx - 1) * calm;
  m.sy = 1 + (m.sy - 1) * calm;
  return m;
}

/** Where each part behind the body is hinged, on the sheet. */
const HINGES: Partial<Record<Mascot, Pt[]>> = {
  ears: [[30, 38], [70, 38]],
  cat: [[30, 40], [70, 40]],
  bunny: [[36, 38], [64, 38]],
  bear: [[28, 40], [72, 40]],
  antenna: [[50, 30]],
  sprout: [[50, 34]],
};

/** A quick double flick once every `period` seconds, −1…1, otherwise 0. */
function twitch(seconds: number, period: number, offset: number): number {
  const p = ((seconds + offset) % period) / period;
  if (p > 0.12) return 0;
  const k = p / 0.12;
  return Math.sin(k * Math.PI * 2) * (1 - k);
}

function swingAngle(kind: Mascot, index: number, seconds: number): number {
  const side = index === 0 ? -1 : 1;
  switch (kind) {
    case "ears":
    case "bear":
      return side * 0.26 * twitch(seconds, 3.4, index * 0.4);
    case "cat":
      return side * 0.3 * twitch(seconds, 2.9, index * 1.3);
    case "bunny": // the ears trail the hop a little
      return side * (0.2 * twitch(seconds, 3.7, index * 0.5) + 0.07 * Math.sin((seconds % 2.6) / 2.6 * Math.PI * 2));
    case "antenna":
      return 0.12 * Math.sin(seconds * 2.2);
    case "sprout":
      return 0.05 * Math.sin(seconds * 2.4);
    default:
      return 0;
  }
}

/** How the index-th part behind the body swings at `seconds`: its hinge in body space, and the angle. */
export function mascotSwing(kind: Mascot, index: number, R: number, seconds: number): { x: number; y: number; angle: number } | null {
  if (kind === "mochi") return null;
  const hinge = HINGES[kind]?.[index];
  if (!hinge) return null;
  const [fx, fy] = FACE[kind];
  const u = R * UNIT;
  return { x: (hinge[0] - fx) * u, y: (hinge[1] - fy) * u, angle: swingAngle(kind, index, seconds) };
}

/** Turns the sheet around a part's hinge, for details drawn on that part. */
function hinged(x: Ctx, kind: Mascot, index: number, seconds: number) {
  const hinge = HINGES[kind]?.[index];
  if (!hinge) return;
  x.translate(hinge[0], hinge[1]);
  x.rotate(swingAngle(kind, index, seconds));
  x.translate(-hinge[0], -hinge[1]);
}

// ── Wearing things. Outfits are drawn for the original body; each mascot says where they go. ──

export type Slot = "hat" | "face" | "neck";

const HATS = new Set(["beanie", "santaHat", "partyHat", "crown", "witchHat", "fez", "gradCap", "bunnyEars", "bow", "witch", "pumpkin", "horns"]);
const FACES = new Set(["sunglasses", "roundGlasses"]);
const NECKS = new Set(["scarf", "teamScarf"]);

/** Where an outfit or accessory sits; null when it is not tied to one place (wings, a collar). */
export function slotOf(item: string): Slot | null {
  return HATS.has(item) ? "hat" : FACES.has(item) ? "face" : NECKS.has(item) ? "neck" : null;
}

/** The original body on the sheet: half its height, which the outfits were drawn against. */
const ORIGINAL_HALF_HEIGHT = 0.88 / UNIT;

/**
 * Per mascot: the line a hat rests on and its size, the size of what is worn on
 * the face, the line a scarf wraps and its size, and how far the head's top
 * sits off centre. Sizes are relative to the original body.
 */
const FIT: Record<Exclude<Mascot, "mochi">, { hat: [number, number]; face: number; neck: [number, number]; lean?: number }> = {
  ghost: { hat: [14, 0.92], face: 0.92, neck: [80, 0.92] },
  clover: { hat: [7, 0.62], face: 1, neck: [92, 0.66] },
  ears: { hat: [26, 1], face: 1, neck: [86, 1] },
  drop: { hat: [22, 0.5], face: 0.96, neck: [92, 0.95] },
  antenna: { hat: [28, 0.96], face: 0.97, neck: [86, 0.97] },
  cat: { hat: [28, 1], face: 1, neck: [86, 1] },
  cloud: { hat: [13, 0.7], face: 1, neck: [86, 1] },
  star: { hat: [15, 0.42], face: 0.72, neck: [80, 0.62] },
  bunny: { hat: [34, 0.9], face: 0.92, neck: [88, 0.92] },
  bear: { hat: [19, 0.95], face: 0.97, neck: [91, 0.95] },
  bean: { hat: [13, 0.68], face: 0.84, neck: [90, 0.8], lean: -9 },
  hex: { hat: [15, 0.7], face: 0.95, neck: [90, 0.8] },
  flame: { hat: [20, 0.42], face: 0.92, neck: [92, 0.92] },
  planet: { hat: [21, 0.86], face: 0.87, neck: [85, 0.87] },
  sprout: { hat: [32, 0.9], face: 0.92, neck: [88, 0.92] },
};

/** Draws something made for the original body where it belongs on this mascot. */
export function wear(x: Ctx, kind: Mascot, slot: Slot | null, R: number, draw: () => void) {
  if (kind === "mochi" || !slot) {
    draw();
    return;
  }
  const fit = FIT[kind];
  const u = R * UNIT;
  const fy = FACE[kind][1];
  let scale = fit.face;
  let dx = 0;
  let dy = 0;
  if (slot === "hat") {
    // The original head's top, scaled, lands on this mascot's crown.
    scale = fit.hat[1];
    dx = (fit.lean ?? 0) * u;
    dy = (fit.hat[0] - fy) * u + ORIGINAL_HALF_HEIGHT * u * scale;
  } else if (slot === "neck") {
    scale = fit.neck[1];
    dy = (fit.neck[0] - fy) * u - ORIGINAL_HALF_HEIGHT * u * scale;
  }
  x.save();
  x.translate(dx, dy);
  x.scale(scale, scale);
  draw();
  x.restore();
}
