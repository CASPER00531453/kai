// The colour of the main bot's body. The original Kai blue unless someone picks
// another one in the settings; the session bots in the pill keep their own.

export type BodyRGB = [number, number, number];

/** Kai blue: the bottom of the body's gradient, and what the setting stores. */
export const DEFAULT_BODY = "#1a7fd4";
const ORIGINAL_TOP: BodyRGB = [0.478, 0.816, 1]; // #7AD0FF

/** The original first, then the ones offered next to it. */
export const BODY_COLORS = [
  DEFAULT_BODY, "#12b5a6", "#2fb457", "#e0a31a", "#ef7a1f", "#e5484d", "#e54b9a", "#8b5cf6", "#7d8794",
];

function parse(hex: string): BodyRGB {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

let hex = DEFAULT_BODY;
let bottom = parse(DEFAULT_BODY);
let top = ORIGINAL_TOP;

export function setBodyColor(raw: unknown) {
  const next = typeof raw === "string" && /^#[0-9a-f]{6}$/i.test(raw) ? raw.toLowerCase() : DEFAULT_BODY;
  if (next === hex) return;
  hex = next;
  bottom = parse(next);
  // The original pair is kept exactly; any other colour gets a lighter top of its own.
  top = next === DEFAULT_BODY
    ? ORIGINAL_TOP
    : [bottom[0] + (1 - bottom[0]) * 0.46, bottom[1] + (1 - bottom[1]) * 0.46, bottom[2] + (1 - bottom[2]) * 0.46];
}

export const bodyHex = () => hex;
export const bodyTop = () => top;
export const bodyBottom = () => bottom;

const css = (c: BodyRGB) => `rgb(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)})`;
export const bodyTopCss = () => css(top);
export const bodyBottomCss = () => css(bottom);

/** A colour of the given hue (0–360) that the dark eyes stay readable on. */
export function hueColor(hue: number): string {
  const s = 0.78, l = 0.47;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + hue / 30) % 12;
    const v = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return Math.round(v * 255).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}
