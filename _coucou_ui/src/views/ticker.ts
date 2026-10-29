// Overview task ticker: the step that just finished, and the one running now.
//
// Two rows in fixed places, one above the other. A new step fades in where it
// belongs; nothing slides across anything else. The sliding version drew each
// row at a position computed every frame, and whenever a frame was late or the
// loop paused, a step was left halfway — one line printed over another.

import { h, svg } from "./dom";
import { ICONS } from "./icons";
import type { AgentTask } from "../core/state";

interface Row {
  el: HTMLElement;
  label: HTMLElement;
  text: string;
}

function makeRow(kind: "done" | "now"): Row {
  const icon = kind === "done" ? svg(ICONS.check, 8, { stroke: 2.2 }) : svg(ICONS.chevronRight, 9, { stroke: 2.4 });
  const label = h("span", { class: kind === "now" ? "tick-text shimmer" : "tick-text" });
  const el = h("div", { class: `ticker-row ${kind}` }, h("span", { class: "tick-icon" }, icon), label);
  return { el, label, text: "" };
}

/** Sets a row's text; a row whose text changes fades in again. */
function setText(row: Row, text: string, animate: boolean) {
  if (row.text === text) return;
  row.text = text;
  row.label.textContent = text;
  row.label.title = text;
  row.el.classList.toggle("empty", text === "");
  if (!animate) return;
  // Restart the CSS animation: drop the class, let the browser notice, add it back.
  row.el.classList.remove("tick-in");
  void row.el.offsetWidth;
  row.el.classList.add("tick-in");
}

export class Ticker {
  readonly el: HTMLElement;
  private done = makeRow("done");
  private now = makeRow("now");
  private seeded = false;

  constructor() {
    this.el = h("div", { class: "ticker" }, this.done.el, this.now.el);
  }

  /** Nothing here depends on the frame loop any more. */
  get animating(): boolean {
    return false;
  }

  sync(task: AgentTask | null) {
    const steps = task?.steps ?? [];
    // The very first fill appears in place; after that every change fades in.
    const animate = this.seeded;
    this.seeded = true;
    setText(this.done, steps.at(-2) ?? "", animate);
    setText(this.now, steps.at(-1) ?? "…", animate);
  }

  /** Kept for the island's frame loop, which calls it while the overview is up. */
  tick(_nowMs: number) {}
}
