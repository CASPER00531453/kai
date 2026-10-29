// The update card — after coucou's views/update.ts: "Kai X is out" with
// Update now · What's new · Later, then the download's progress, or what went
// wrong. Green wash, the mascot on the left like the other cards.

import { h, clear } from "./dom";
import { washRGBA } from "../core/layout";
import { prefs, runUpdate, tx, updatePhase, type UpdatePhase } from "../core/prefs";
import type { ViewHost } from "./views";

function btn(label: string, kind: "primary" | "secondary", onClick: () => void): HTMLButtonElement {
  return h("button", { class: `btn ${kind}`, onclick: onClick }, h("span", { text: label }));
}

const fill = (text: string, v: string, p = "") => text.replace("{v}", v).replace("{p}", p);

export function buildUpdate(collapse: () => void, later: (version: string) => void): ViewHost {
  const title = h("div", { class: "title one-line" });
  const line = h("div", { class: "sub update-line" });
  const bar = h("div", { class: "update-bar" }, h("div", { class: "fill" }));
  const row = h("div", { class: "actions" });
  const stack = h("div", { class: "stack" }, title, line, bar, row);
  stack.style.padding = "4px 16px 4px 116px";
  const card = h("div", { class: "card wash" }, stack);
  card.style.setProperty("--wash", washRGBA("green"));
  const el = h("div", { class: "view" }, card);

  let phase: UpdatePhase = { phase: "idle", fraction: 0, error: "" };
  let poller: number | null = null;
  // The buttons are only rebuilt when what they offer changes: rebuilding them
  // between a mouse-down and a mouse-up would swallow the click.
  let rowKey = "";
  const buttons = (key: string, make: () => HTMLElement[]) => {
    key = `${key}~${tx("ok")}`;
    if (key === rowKey) return;
    rowKey = key;
    clear(row);
    row.append(...make());
  };

  const follow = () => {
    if (poller != null) return;
    poller = window.setInterval(async () => {
      phase = await updatePhase();
      if (phase.phase !== "downloading" && poller != null) {
        window.clearInterval(poller);
        poller = null;
      }
      host.sync();
    }, 400);
  };

  const host: ViewHost = {
    el,
    sync() {
      const p = prefs();
      const latest = p?.updateLatest ?? "";
      const have = fill(tx("updHave"), p?.version ?? "");
      (bar as HTMLElement).style.display = "none";
      title.textContent = fill(tx("updOut"), latest);
      title.title = title.textContent;

      if (phase.phase === "error") {
        title.textContent = tx("updFailed");
        line.textContent = phase.error;
        buttons("error", () => [
          btn(tx("updGet"), "primary", () => void runUpdate("page")),
          btn(tx("ok"), "secondary", () => { phase = { phase: "idle", fraction: 0, error: "" }; void runUpdate("dismiss"); collapse(); }),
        ]);
        return;
      }
      if (phase.phase === "downloading") {
        (bar as HTMLElement).style.display = "";
        const pct = Math.round(phase.fraction * 100);
        (bar.firstChild as HTMLElement).style.width = `${pct}%`;
        line.textContent = fill(tx("updDownloading"), latest, String(pct));
        buttons("busy", () => []);
        return;
      }
      if (phase.phase === "installing") {
        line.textContent = tx("updInstalling");
        buttons("busy", () => []);
        return;
      }
      // The release's first line of notes, else what you have now.
      const headline = (p?.updateNotes ?? "").split("\n").map((l) => l.replace(/^[#*\s-]+/, "").trim()).find(Boolean);
      line.textContent = headline ? `${headline} · ${have}` : have;
      buttons("offer", () => [
        btn(tx("updNow"), "primary", async () => {
          phase = { phase: "downloading", fraction: 0, error: "" };
          host.sync();
          await runUpdate("install");
          follow();
        }),
        btn(tx("updNews"), "secondary", () => void runUpdate("page")),
        btn(tx("updLater"), "secondary", () => { later(latest); collapse(); }),
      ]);
    },
  };
  return host;
}
