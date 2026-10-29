// The task queue (taskqueue.py on the host): what Claude Code should do next,
// typed while it works. When a turn ends, Kai hands Claude the first task and
// it goes on without stopping.

import { h, clear } from "./dom";
import { washRGBA } from "../core/layout";
import { State } from "../core/state";
import { turkish } from "../core/prefs";
import type { ViewHost } from "./views";

export interface QueueItem { id: string; text: string; at: number }

type Host = { queue?: (op: string, arg: string) => Promise<string> };
const host = () => (window as unknown as { pywebview?: { api?: Host } }).pywebview?.api;

/** The queue as the host last told it; the overview shows its length. */
export const Queue = {
  items: [] as QueueItem[],
  /** Opens the queue card; set by buildViews. */
  open: () => {},
  async run(op: "list" | "add" | "remove" | "clear", arg = "") {
    try {
      const raw = await host()?.queue?.(op, arg);
      if (raw) Queue.items = JSON.parse(raw) as QueueItem[];
    } catch {
      /* the list stays as it was */
    }
    State.notify();
  },
};

const L = (tr: string, en: string) => (turkish() ? tr : en);

export function buildQueue(back: () => void): ViewHost {
  const input = h("input", { class: "queue-input", maxlength: "1500" }) as HTMLInputElement;
  const add = h("button", { class: "btn primary", onclick: () => void submit() }, h("span"));
  const list = h("div", { class: "queue-list" });
  const hint = h("div", { class: "sub queue-hint" });
  const done = h("button", { class: "btn secondary", onclick: back }, h("span"));
  const stack = h("div", { class: "stack" },
    h("div", { class: "who-row" }, h("span", { class: "n", style: "color:#4DB5FF" })),
    h("div", { class: "queue-row" }, input, add),
    list, hint, h("div", { class: "actions" }, done));
  stack.style.padding = "4px 16px 4px 116px";
  const card = h("div", { class: "card wash" }, stack);
  card.style.setProperty("--wash", washRGBA("indigo"));
  const el = h("div", { class: "view" }, card);

  async function submit() {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    await Queue.run("add", text);
    input.focus();
  }
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void submit();
    }
    e.stopPropagation();
  });

  let key = "";
  return {
    el,
    focus() {
      void Queue.run("list");
      input.focus();
    },
    sync() {
      (stack.firstChild!.firstChild as HTMLElement).textContent = L("Görev sırası", "Task queue");
      input.placeholder = L("Claude bitirince ne yapsın?", "What should Claude do next?");
      (add.firstChild as HTMLElement).textContent = L("Ekle", "Add");
      (done.firstChild as HTMLElement).textContent = L("Tamam", "Done");
      hint.textContent = Queue.items.length
        ? L("Claude işini bitirince sıradakine kendisi geçer.", "When Claude finishes, it moves on to the next one by itself.")
        : L("Sıra boş. Bir iş yaz, Enter'a bas.", "The queue is empty. Type a task and press Enter.");
      // Rebuilt only when the list changes: a rebuild between a mouse-down and
      // a mouse-up would swallow the click on ×.
      const next = Queue.items.map((i) => i.id).join("|") + turkish();
      if (next === key) return;
      key = next;
      clear(list);
      Queue.items.slice(0, 4).forEach((item, index) => {
        list.append(h("div", { class: "queue-item" },
          h("span", { class: "queue-no", text: `${index + 1}.` }),
          h("span", { class: "queue-text", text: item.text, title: item.text }),
          h("button", { class: "queue-del", title: L("Sil", "Remove"), text: "×", onclick: () => void Queue.run("remove", item.id) })));
      });
      if (Queue.items.length > 4) list.append(h("div", { class: "sub", text: L(`+${Queue.items.length - 4} iş daha`, `+${Queue.items.length - 4} more`) }));
    },
  };
}
