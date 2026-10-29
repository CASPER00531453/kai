// The code view: Claude Code's current edit as a diff, with the tools it has
// run listed beside Mochi. Opened with the arrow on Kai's card.

import { h, svg, clear } from "./dom";
import { ICONS } from "./icons";
import { CodeFeed, type CodeLine } from "../core/codefeed";
import { tx } from "../core/prefs";
import { State } from "../core/state";
import type { ViewHost } from "./views";

/** Characters typed per second when a new edit comes in. */
const TYPE_SPEED = 140;

const BADGES: Record<string, string> = {
  ts: "#3178C6", tsx: "#3178C6", js: "#E8B923", jsx: "#E8B923", py: "#3572A5", rs: "#DEA584",
  go: "#00ADD8", css: "#8B5CF6", html: "#E34C26", json: "#6B7079", md: "#6B7079", cs: "#178600",
};

const KEYWORDS =
  "import|from|export|const|let|var|function|return|if|else|elif|for|while|class|def|async|await|new|try|" +
  "except|catch|finally|with|as|in|of|type|interface|extends|public|private|static|void|lambda|yield|raise|" +
  "throw|pass|break|continue|and|or|not|is|None|True|False|true|false|null|undefined|self|this";

/** Colours a line of code well enough to read: comments, strings, numbers, keywords, types, calls. */
function paint(target: HTMLElement, line: string, hashComments: boolean) {
  const comment = hashComments ? "(\\/\\/.*$|#.*$)" : "(\\/\\/.*$)";
  const pattern = new RegExp(
    comment +
      "|(\"(?:[^\"\\\\]|\\\\.)*\"|'(?:[^'\\\\]|\\\\.)*'|`(?:[^`\\\\]|\\\\.)*`)" +
      "|\\b(\\d+(?:\\.\\d+)?)\\b" +
      `|\\b(${KEYWORDS})\\b` +
      "|\\b([A-Z][A-Za-z0-9_]*)\\b" +
      "|\\b([A-Za-z_]\\w*)(?=\\()",
    "g",
  );
  const classes = ["", "tok-comment", "tok-string", "tok-number", "tok-keyword", "tok-type", "tok-call"];
  let at = 0;
  for (const match of line.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > at) target.append(line.slice(at, start));
    const group = match.findIndex((part, i) => i > 0 && part != null);
    target.append(h("span", { class: classes[group] ?? "", text: match[0] }));
    at = start + match[0].length;
  }
  if (at < line.length) target.append(line.slice(at));
}

export function buildCode(back: () => void): ViewHost {
  const name = h("div", { class: "code-name" });
  const steps = h("div", { class: "code-steps" });
  const side = h("div", { class: "code-side" }, name, h("div", { class: "code-sub", text: "Claude Code" }), steps);

  const badge = h("span", { class: "code-badge" });
  const file = h("span", { class: "code-file" });
  const path = h("span", { class: "code-path" });
  const tab = h("div", { class: "code-tab" }, h("div", { class: "code-tab-on" }, badge, file, h("i", {})), path);
  const body = h("div", { class: "code-lines" });
  const close = h(
    "button",
    { class: "icon-btn jump", style: "transform:rotate(180deg)", onclick: back },
    svg(ICONS.arrowUpRight, 8),
  );
  const panel = h("div", { class: "code-panel" }, tab, body);
  const el = h("div", { class: "view code-view" }, side, panel, close);

  let shownStamp = -1;
  let shownKey = "";
  let typing: number | null = null;
  let typedFrom = 0;

  function stopTyping() {
    if (typing != null) window.clearInterval(typing);
    typing = null;
  }

  /** Builds every line; added lines start empty when they are about to be typed. */
  function render(lines: CodeLine[], animate: boolean) {
    stopTyping();
    clear(body);
    const hash = /\.(py|sh|ps1|ya?ml|toml|rb)$/i.test(CodeFeed.file);
    const fresh: { src: HTMLElement; text: string }[] = [];
    for (const line of lines) {
      const src = h("span", { class: "src" });
      if (animate && line.kind === "add") fresh.push({ src, text: line.text });
      else paint(src, line.text, hash);
      body.append(
        h(
          "div",
          { class: `code-line ${line.kind}` },
          h("span", { class: "no", text: line.no == null ? "" : String(line.no) }),
          h("span", { class: "sign", text: line.kind === "del" ? "-" : line.kind === "add" ? "+" : "" }),
          src,
        ),
      );
    }
    if (fresh.length === 0) return;
    typedFrom = performance.now();
    const caret = h("i", { class: "caret" });
    typing = window.setInterval(() => {
      let budget = Math.floor(((performance.now() - typedFrom) / 1000) * TYPE_SPEED);
      let pending = false;
      for (const item of fresh) {
        const take = Math.min(item.text.length, Math.max(0, budget));
        budget -= item.text.length;
        clear(item.src);
        if (take >= item.text.length) {
          paint(item.src, item.text, hash);
        } else {
          item.src.append(item.text.slice(0, take));
          if (!pending) item.src.append(caret);
          pending = true;
        }
      }
      if (!pending) {
        stopTyping();
        State.notify();
      }
    }, 30);
  }

  return {
    el,
    sync() {
      name.textContent = State.tasks.find((t) => t.id === "integration_claude")?.name ?? "Kai";

      clear(steps);
      for (const step of CodeFeed.steps) {
        steps.append(h("div", { class: `code-step ${step.state}` }, h("i", {}), h("span", { text: step.tool })));
      }
      steps.append(
        h("div", { class: `code-step ${CodeFeed.finished ? "done" : "wait"}` }, h("i", {}), h("span", { text: tx("codeDone") })),
      );

      if (CodeFeed.lines.length === 0) {
        if (shownKey !== "empty") {
          shownKey = "empty";
          stopTyping();
          tab.style.visibility = "hidden";
          clear(body);
          body.append(h("div", { class: "code-empty", text: tx("codeIdle") }));
        }
        return;
      }
      tab.style.visibility = "";
      const ext = (CodeFeed.file.split(".").pop() || "").toLowerCase();
      badge.textContent = CodeFeed.file === "terminal" ? ">_" : ext.slice(0, 3).toUpperCase();
      badge.style.background = BADGES[ext] ?? "#3A3F4B";
      file.textContent = CodeFeed.file;
      path.textContent = CodeFeed.path === CodeFeed.file ? "" : CodeFeed.path.replace(/\\/g, "/").split("/").slice(-3).join("/");

      // A new edit is typed out once; the real patch then replaces it without typing again.
      const key = `${CodeFeed.stamp}:${CodeFeed.settled}:${CodeFeed.lines.length}`;
      if (key === shownKey) return;
      const animate = CodeFeed.stamp !== shownStamp;
      // Same edit, still being typed: let it finish. It asks for a sync when it is done.
      if (!animate && typing != null) return;
      shownKey = key;
      shownStamp = CodeFeed.stamp;
      render(CodeFeed.lines, animate);
    },
  };
}
