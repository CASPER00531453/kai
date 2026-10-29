// Things Kai can wear. Drawn in the body's own space: origin at the centre of
// the body, `rx`/`ry` its half-width and half-height, `R` the engine's base unit.
// The first set is for Halloween.

export const ACCESSORIES = ["none", "witch", "pumpkin", "bat", "horns", "vampire"] as const;
export type Accessory = (typeof ACCESSORIES)[number];

type Ctx = CanvasRenderingContext2D;

const NIGHT = "#1b1326";
const PURPLE = "#34224d";
const ORANGE = "#F28C28";

/** Drawn before the body, so the body covers the part that tucks behind it. */
export function drawAccessoryBehind(x: Ctx, kind: string, R: number, rx: number, ry: number) {
  if (kind === "bat") {
    x.fillStyle = NIGHT;
    for (const sd of [-1, 1]) {
      x.beginPath();
      x.moveTo(sd * rx * 0.55, -ry * 0.15);
      x.quadraticCurveTo(sd * rx * 1.05, -ry * 1.05, sd * rx * 1.42, -ry * 0.8);
      // Three scallops along the bottom edge of the wing.
      x.quadraticCurveTo(sd * rx * 1.3, -ry * 0.35, sd * rx * 1.36, ry * 0.05);
      x.quadraticCurveTo(sd * rx * 1.14, -ry * 0.12, sd * rx * 1.08, ry * 0.3);
      x.quadraticCurveTo(sd * rx * 0.9, ry * 0.08, sd * rx * 0.7, ry * 0.42);
      x.closePath();
      x.fill();
    }
  } else if (kind === "vampire") {
    // A high collar standing up behind the head.
    for (const sd of [-1, 1]) {
      x.beginPath();
      x.moveTo(sd * rx * 0.45, ry * 0.3);
      x.lineTo(sd * rx * 1.32, -ry * 0.55);
      x.quadraticCurveTo(sd * rx * 1.25, ry * 0.35, sd * rx * 0.85, ry * 0.95);
      x.closePath();
      x.fillStyle = "#B3122B";
      x.fill();
      x.beginPath();
      x.moveTo(sd * rx * 0.6, ry * 0.3);
      x.lineTo(sd * rx * 1.18, -ry * 0.28);
      x.quadraticCurveTo(sd * rx * 1.1, ry * 0.3, sd * rx * 0.85, ry * 0.7);
      x.closePath();
      x.fillStyle = NIGHT;
      x.fill();
    }
  }
}

/** Drawn over the finished face. */
export function drawAccessoryFront(x: Ctx, kind: string, R: number, rx: number, ry: number) {
  if (kind === "witch") {
    x.save();
    x.translate(0, -ry * 0.8);
    x.rotate(-0.1);
    x.fillStyle = NIGHT;
    x.beginPath();
    x.ellipse(0, 0, rx * 0.98, R * 0.17, 0, 0, Math.PI * 2);
    x.fill();
    // The cone, with its tip flopping to one side.
    x.fillStyle = PURPLE;
    x.beginPath();
    x.moveTo(-rx * 0.56, -R * 0.02);
    x.quadraticCurveTo(-rx * 0.2, -R * 0.5, rx * 0.34, -R * 0.9);
    x.quadraticCurveTo(rx * 0.2, -R * 0.42, rx * 0.56, -R * 0.02);
    x.quadraticCurveTo(0, R * 0.12, -rx * 0.56, -R * 0.02);
    x.fill();
    x.fillStyle = ORANGE;
    x.beginPath();
    x.moveTo(-rx * 0.55, -R * 0.03);
    x.quadraticCurveTo(0, R * 0.11, rx * 0.55, -R * 0.03);
    x.lineTo(rx * 0.45, -R * 0.17);
    x.quadraticCurveTo(0, -R * 0.04, -rx * 0.44, -R * 0.2);
    x.closePath();
    x.fill();
    x.strokeStyle = "#FFD86B";
    x.lineWidth = Math.max(1, R * 0.045);
    x.strokeRect(-R * 0.09, -R * 0.1, R * 0.18, R * 0.15);
    x.restore();
  } else if (kind === "pumpkin") {
    // A little jack-o'-lantern sitting on the head.
    const py = -ry * 1.0;
    const w = R * 0.52;
    const h = R * 0.4;
    x.fillStyle = "#3E8E41";
    x.beginPath();
    x.moveTo(-R * 0.05, py - h * 0.85);
    x.quadraticCurveTo(R * 0.02, py - h * 1.5, R * 0.2, py - h * 1.45);
    x.lineTo(R * 0.17, py - h * 1.2);
    x.quadraticCurveTo(R * 0.08, py - h * 1.2, R * 0.07, py - h * 0.85);
    x.closePath();
    x.fill();
    for (const [dx, shade] of [[-0.55, "#D9731A"], [0.55, "#D9731A"], [0, ORANGE]] as const) {
      x.fillStyle = shade;
      x.beginPath();
      x.ellipse(dx * w, py, w * 0.62, h, 0, 0, Math.PI * 2);
      x.fill();
    }
    x.fillStyle = "#3a1c05";
    for (const sd of [-1, 1]) {
      x.beginPath();
      x.moveTo(sd * w * 0.42, py - h * 0.32);
      x.lineTo(sd * w * 0.62, py + h * 0.02);
      x.lineTo(sd * w * 0.2, py + h * 0.02);
      x.closePath();
      x.fill();
    }
    x.beginPath();
    x.moveTo(-w * 0.5, py + h * 0.3);
    x.quadraticCurveTo(0, py + h * 0.85, w * 0.5, py + h * 0.3);
    x.quadraticCurveTo(0, py + h * 0.5, -w * 0.5, py + h * 0.3);
    x.fill();
  } else if (kind === "horns") {
    x.fillStyle = "#E0342B";
    for (const sd of [-1, 1]) {
      x.beginPath();
      x.moveTo(sd * rx * 0.3, -ry * 0.86);
      x.quadraticCurveTo(sd * rx * 0.42, -ry * 1.45, sd * rx * 0.78, -ry * 1.5);
      x.quadraticCurveTo(sd * rx * 0.7, -ry * 1.1, sd * rx * 0.68, -ry * 0.7);
      x.closePath();
      x.fill();
    }
  } else if (kind === "vampire") {
    x.fillStyle = "#fff";
    for (const sd of [-1, 1]) {
      x.beginPath();
      x.moveTo(sd * R * 0.07, ry * 0.42);
      x.lineTo(sd * R * 0.23, ry * 0.42);
      x.lineTo(sd * R * 0.15, ry * 0.7);
      x.closePath();
      x.fill();
    }
  }
}
