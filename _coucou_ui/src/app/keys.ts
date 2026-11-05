// The dictation key: a preset (hook.py DICTATION_KEYS) or a shortcut of one's own,
// "keys:12+10+46" (Windows virtual keys, hex), recorded here from the keys held.

import { h } from "../views/dom";
import { L } from "./ui";

export const PRESETS: [string, string][] = [
  ["rctrl", "Sağ Ctrl"], ["rshift", "Sağ Shift"], ["ctrlwin", "Ctrl + Win"],
  ["lctrl", "Sol Ctrl"], ["lshift", "Sol Shift"], ["lalt", "Sol Alt"],
];

// KeyboardEvent.code for the keys whose sides matter; the rest go by keyCode,
// which is the virtual key for letters, digits and F keys.
const SIDED: Record<string, number> = {
  ControlLeft: 0xa2, ControlRight: 0xa3, ShiftLeft: 0xa0, ShiftRight: 0xa1,
  AltLeft: 0xa4, AltRight: 0xa5, MetaLeft: 0x5b, MetaRight: 0x5c,
};
const NAMES: Record<number, string> = {
  0xa2: "Sol Ctrl", 0xa3: "Sağ Ctrl", 0xa0: "Sol Shift", 0xa1: "Sağ Shift",
  0xa4: "Sol Alt", 0x5b: "Win", 0x5c: "Win", 0x20: "Space", 0x09: "Tab",
  0x14: "Caps Lock", 0x2d: "Insert", 0x24: "Home", 0x23: "End", 0x21: "Page Up", 0x22: "Page Down",
};

function vkOf(e: KeyboardEvent): number {
  return SIDED[e.code] ?? e.keyCode;
}

function vkName(vk: number): string {
  if (NAMES[vk]) return L(NAMES[vk], NAMES[vk].replace("Sol", "Left").replace("Sağ", "Right"));
  if (vk >= 0x70 && vk <= 0x87) return `F${vk - 0x6f}`;
  if ((vk >= 0x30 && vk <= 0x39) || (vk >= 0x41 && vk <= 0x5a)) return String.fromCharCode(vk);
  return `#${vk.toString(16)}`;
}

/** The keys to show for a choice, as keycaps. */
export function keyLabel(value: string): string[] {
  if (value.startsWith("keys:")) {
    return value.slice(5).split("+").filter(Boolean).map((x) => vkName(parseInt(x, 16)));
  }
  const preset = PRESETS.find(([v]) => v === value)?.[1] ?? "Sağ Ctrl";
  return preset.split(" + ").map((x) => L(x, x.replace("Sol", "Left").replace("Sağ", "Right")));
}

/**
 * "A shortcut of your own…": press the keys together, let go, they are kept.
 * AltGr stays Kai's talk key and Escape cancels.
 */
export function recordButton(save: (value: string) => void): HTMLButtonElement {
  const idle = L("Kendi kısayolun…", "Your own shortcut…");
  const b = h("button", { class: "a-btn ghost", text: idle }) as HTMLButtonElement;
  let held = new Set<number>();
  let combo: number[] = [];
  const stop = () => {
    window.removeEventListener("keydown", down, true);
    window.removeEventListener("keyup", up, true);
    b.textContent = idle;
    b.classList.remove("recording");
  };
  const down = (e: KeyboardEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.code === "Escape") return stop();
    const vk = vkOf(e);
    if (vk === 0xa5) {
      b.textContent = L("AltGr Kai ile konuşmak için, başka tuş seç", "AltGr is for talking to Kai, pick another");
      return;
    }
    held.add(vk);
    if (!combo.includes(vk) && combo.length < 4) combo.push(vk);
    b.textContent = combo.map(vkName).join(" + ");
  };
  const up = (e: KeyboardEvent) => {
    e.preventDefault();
    held.delete(vkOf(e));
    if (held.size || !combo.length) return;
    const value = "keys:" + combo.map((k) => k.toString(16).padStart(2, "0")).join("+");
    stop();
    save(value);
  };
  b.addEventListener("click", () => {
    held = new Set();
    combo = [];
    b.textContent = L("Tuşlara birlikte bas, bırak…", "Press the keys together, let go…");
    b.classList.add("recording");
    window.addEventListener("keydown", down, true);
    window.addEventListener("keyup", up, true);
  });
  return b;
}
