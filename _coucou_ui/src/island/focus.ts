// Focus mode: twenty-five minutes of focus, five of break, round and round until
// it is stopped. The countdown sits in the middle of the compact island, the
// mascot is serious while you focus and yawns on the break, and while you focus
// finished turns and other news only take a badge (hooks.ts): requests and
// questions still come up, since Claude waits on them.

import { Sound } from "../core/sound";
import { State } from "../core/state";
import { turkish } from "../core/prefs";

export const FOCUS_MIN = 25;
export const BREAK_MIN = 5;

type Phase = "off" | "focus" | "break";

interface FocusHost {
  emote(name: "yawn" | "proud" | "happy"): void;
  setLook(phase: Phase): void;
  reveal(): void;
}

let phase: Phase = "off";
let endsAt = 0;
let timer: number | null = null;
let host: FocusHost | null = null;

const brand = () => document.getElementById("kai-brand");

export const Focus = {
  get phase(): Phase {
    return phase;
  },
  /** Focusing right now: news is kept quiet. */
  get focusing(): boolean {
    return phase === "focus";
  },
  attach(h: FocusHost) {
    host = h;
  },
  toggle() {
    if (phase === "off") start("focus");
    else stop();
  },
};

function start(next: Exclude<Phase, "off">) {
  phase = next;
  endsAt = Date.now() + (next === "focus" ? FOCUS_MIN : BREAK_MIN) * 60_000;
  host?.setLook(next);
  if (next === "break") host?.emote("yawn");
  else host?.emote("proud");
  timer ??= window.setInterval(tick, 1000);
  tick();
  State.notify();
}

function stop() {
  phase = "off";
  if (timer != null) window.clearInterval(timer);
  timer = null;
  host?.setLook("off");
  const el = brand();
  if (el) {
    el.classList.remove("focus", "break");
    if (!el.classList.contains("recording") && !el.classList.contains("note")) el.textContent = "Kai V2";
  }
  State.notify();
}

function tick() {
  const left = Math.max(0, Math.round((endsAt - Date.now()) / 1000));
  if (left === 0) {
    // The turn of the clock: a sound, the island shows itself, the other phase starts.
    Sound.play(phase === "focus" ? "finish" : "work");
    host?.reveal();
    start(phase === "focus" ? "break" : "focus");
    return;
  }
  const el = brand();
  // A recording's clock or a short note owns the middle of the pill meanwhile.
  if (!el || el.classList.contains("recording") || el.classList.contains("note")) return;
  const mm = String(Math.floor(left / 60)).padStart(2, "0");
  const ss = String(left % 60).padStart(2, "0");
  const tr = turkish();
  el.classList.toggle("focus", phase === "focus");
  el.classList.toggle("break", phase === "break");
  el.textContent = `${phase === "focus" ? (tr ? "Odak" : "Focus") : (tr ? "Mola" : "Break")} ${mm}:${ss}`;
}
