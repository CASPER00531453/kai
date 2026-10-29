// Small building blocks for the Kai window's pages.

import { h } from "../views/dom";

let turkish = true;
export const setTurkish = (on: boolean) => {
  turkish = on;
  document.documentElement.lang = on ? "tr" : "en";
};
/** Turkish first, English when the app's language is English. */
export const L = (tr: string, en: string) => (turkish ? tr : en);

export function card(title: string | null, ...children: (Node | null | false)[]): HTMLElement {
  return h("section", { class: "a-card" }, title ? h("h3", { class: "a-card-title", text: title }) : null, ...children);
}

export function row(label: string, hint: string | null, control: Node | null): HTMLElement {
  return h(
    "div",
    { class: "a-row" },
    h("div", { class: "a-row-text" }, h("div", { class: "a-row-label", text: label }), hint ? h("div", { class: "a-row-hint", text: hint }) : null),
    control ? h("div", { class: "a-row-control" }, control) : null,
  );
}

export function toggle(on: boolean, change: (on: boolean) => void): HTMLElement {
  const el = h("button", { class: on ? "a-switch on" : "a-switch", "aria-pressed": on ? "true" : "false" });
  el.addEventListener("click", () => {
    const next = !el.classList.contains("on");
    el.classList.toggle("on", next);
    el.setAttribute("aria-pressed", String(next));
    change(next);
  });
  return el;
}

export function select(options: [string, string][], value: string, change: (v: string) => void): HTMLSelectElement {
  const el = h("select", { class: "a-select" }) as HTMLSelectElement;
  for (const [label, v] of options) {
    const o = h("option", { value: v, text: label }) as HTMLOptionElement;
    if (v === value) o.selected = true;
    el.append(o);
  }
  el.addEventListener("change", () => change(el.value));
  return el;
}

/** A row of choices where one is on. */
export function segmented(options: [string, string][], value: string, change: (v: string) => void): HTMLElement {
  const wrap = h("div", { class: "a-seg" });
  for (const [label, v] of options) {
    const b = h("button", { class: v === value ? "on" : "", text: label });
    b.addEventListener("click", () => {
      wrap.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      change(v);
    });
    wrap.append(b);
  }
  return wrap;
}

export function button(text: string, onclick: () => void, kind: "primary" | "ghost" | "danger" | "" = ""): HTMLButtonElement {
  const b = h("button", { class: `a-btn ${kind}`, text }) as HTMLButtonElement;
  b.addEventListener("click", onclick);
  return b;
}

export function input(value: string, placeholder: string, change: (v: string) => void, opts: { type?: string; wide?: boolean } = {}): HTMLInputElement {
  const el = h("input", { class: opts.wide ? "a-input wide" : "a-input", value, placeholder, type: opts.type ?? "text", spellcheck: "false" }) as HTMLInputElement;
  el.value = value;
  el.addEventListener("change", () => change(el.value));
  return el;
}

export function keycap(...keys: string[]): HTMLElement {
  const wrap = h("span", { class: "a-keys" });
  keys.forEach((k, i) => {
    if (i) wrap.append(h("span", { class: "a-plus", text: "+" }));
    wrap.append(h("kbd", { class: "a-kbd", text: k }));
  });
  return wrap;
}

export function pill(text: string, color: string): HTMLElement {
  return h("span", { class: "a-pill", style: `--c:${color}`, text });
}

let toastTimer: number | null = null;
export function toast(text: string) {
  let el = document.getElementById("a-toast");
  if (!el) {
    el = h("div", { id: "a-toast" });
    document.body.append(el);
  }
  el.textContent = text;
  el.classList.add("on");
  if (toastTimer != null) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => el?.classList.remove("on"), 2600);
}

export function mb(bytes: number): string {
  return bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.round(bytes / 1e6)} MB`;
}

export function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const hh = Math.floor(s / 3600);
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return hh ? `${hh}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function when(epoch: number): string {
  const d = new Date(epoch * 1000);
  return d.toLocaleString(turkish ? "tr-TR" : "en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
