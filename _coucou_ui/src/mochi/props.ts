// What Kai holds while the paired phone looks at this computer (phone_view.py):
// a camera to its eye for the camera, a magnifying glass for the screen. Drawn
// over the mascot, so whoever is at the computer always sees that someone looks.

export type PhoneView = "camera" | "screen" | null;

/**
 * `cx`, `cy` is the middle of the mascot's face and `R` its radius, as in
 * BotEngine.draw (R = width * 0.3). `t` is in seconds; `presence` 0…1 brings the
 * prop in and out.
 */
export function drawViewProp(x: CanvasRenderingContext2D, view: Exclude<PhoneView, null>, cx: number, cy: number, R: number, t: number, presence: number) {
  if (presence <= 0.01) return;
  // The right eye of the ghost: sheet (60, 50), one unit = R * 0.031.
  const ex = cx + R * 0.31;
  const ey = cy - R * 0.02;
  x.save();
  x.globalAlpha = Math.min(1, presence);
  // It comes up from below while it appears.
  x.translate(0, (1 - presence) * R * 0.8);
  if (view === "camera") camera(x, ex, ey, R, t);
  else magnifier(x, ex, ey, R, t);
  x.restore();
}

function hand(x: CanvasRenderingContext2D, hx: number, hy: number, R: number) {
  x.fillStyle = "#e9eef7";
  x.beginPath();
  x.ellipse(hx, hy, R * 0.14, R * 0.12, 0, 0, Math.PI * 2);
  x.fill();
}

function camera(x: CanvasRenderingContext2D, ex: number, ey: number, R: number, t: number) {
  const w = R * 0.95;
  const h = R * 0.62;
  const left = ex - w * 0.42;
  const top = ey - h / 2;
  x.shadowColor = "rgba(0,0,0,0.45)";
  x.shadowBlur = R * 0.12;
  x.fillStyle = "#23262d";
  x.beginPath();
  x.roundRect(left, top, w, h, R * 0.12);
  x.fill();
  x.shadowBlur = 0;
  // The top bump and the shutter button.
  x.fillStyle = "#2f333c";
  x.beginPath();
  x.roundRect(left + w * 0.58, top - h * 0.18, w * 0.28, h * 0.22, R * 0.04);
  x.fill();
  x.fillStyle = "#f4505e";
  x.beginPath();
  x.arc(left + w * 0.2, top + h * 0.02, R * 0.045, 0, Math.PI * 2);
  x.fill();
  // The lens right over the eye, with a glint that turns.
  x.fillStyle = "#101216";
  x.beginPath();
  x.arc(ex, ey, h * 0.36, 0, Math.PI * 2);
  x.fill();
  x.strokeStyle = "#5b6170";
  x.lineWidth = Math.max(1, R * 0.05);
  x.stroke();
  const glow = x.createRadialGradient(ex, ey, 0, ex, ey, h * 0.3);
  glow.addColorStop(0, "#4db5ff");
  glow.addColorStop(1, "#0b2a44");
  x.fillStyle = glow;
  x.beginPath();
  x.arc(ex, ey, h * 0.26, 0, Math.PI * 2);
  x.fill();
  x.fillStyle = "rgba(255,255,255,0.75)";
  x.beginPath();
  x.arc(ex + Math.cos(t * 1.3) * h * 0.1, ey - h * 0.1, h * 0.06, 0, Math.PI * 2);
  x.fill();
  // The red light that says it is recording, blinking.
  if (Math.floor(t * 2) % 2 === 0) {
    x.fillStyle = "#ff3b4a";
    x.beginPath();
    x.arc(left + w * 0.9, top + h * 0.2, R * 0.05, 0, Math.PI * 2);
    x.fill();
  }
  hand(x, left + w * 0.12, top + h * 0.95, R);
  hand(x, left + w * 0.95, top + h * 0.9, R);
}

function magnifier(x: CanvasRenderingContext2D, ex: number, ey: number, R: number, t: number) {
  // It sways a little, as if looking over the screen.
  const sway = Math.sin(t * 1.6) * R * 0.05;
  const gx = ex + sway;
  const gy = ey;
  const r = R * 0.34;
  // The handle, down to the hand.
  const hx = gx + r * 1.5;
  const hy = gy + r * 1.6;
  x.strokeStyle = "#8a5a2b";
  x.lineCap = "round";
  x.lineWidth = R * 0.13;
  x.beginPath();
  x.moveTo(gx + r * 0.72, gy + r * 0.72);
  x.lineTo(hx, hy);
  x.stroke();
  // The glass: the eye shows through, bigger.
  x.fillStyle = "rgba(170,220,255,0.28)";
  x.beginPath();
  x.arc(gx, gy, r, 0, Math.PI * 2);
  x.fill();
  x.strokeStyle = "#c9ced8";
  x.lineWidth = R * 0.075;
  x.stroke();
  x.fillStyle = "rgba(255,255,255,0.55)";
  x.beginPath();
  x.ellipse(gx - r * 0.35, gy - r * 0.38, r * 0.22, r * 0.12, -0.6, 0, Math.PI * 2);
  x.fill();
  hand(x, hx, hy, R);
}
