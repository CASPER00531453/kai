// Island views — DOM ports of IslandViewContent.swift. Paddings, font sizes,
// colours and wording are copied from the Swift views so both platforms read
// identically.

import { PICKABLE, mascotLabel, parseMascot } from "../mochi/mascots";
import { BODY_COLORS, bodyHex, hueColor, setBodyColor } from "../mochi/palette";
import { buildWardrobe } from "./wardrobe";
import { buildUpdate } from "./update";
import { updateLater } from "../island/update";
import { h, svg, clear, dot } from "./dom";
import { ICONS } from "./icons";
import { Ticker } from "./ticker";
import { State, type AgentTask } from "../core/state";
import { setAgent, loadPrefs, openHostSettings, pillName, prefs, runUpdate, setPref, tx } from "../core/prefs";
import { washRGBA, type IslandViewName, type Wash } from "../core/layout";
import { createMiniBot, pruneMiniBots } from "../mochi/minibots";
import { buildPrompt } from "./chat";
import { buildCode } from "./code";
import { buildChoose, buildUpload, buildUploading } from "./upload";
import { renderIntegrationCard, type IntegrationCardHooks } from "./integrations";
import { usageChip, usageColor, usagePct } from "../core/usage";
import { Turn } from "../core/codefeed";
import { turkish } from "../core/prefs";
import { Focus } from "../island/focus";
import { Queue, buildQueue } from "./queue";
import { buildSummary } from "./summary";

export type Decision = "allow" | "always" | "deny" | "plan_auto" | "plan_default" | "plan_change";

export interface ViewActions {
  setView(v: IslandViewName): void;
  collapse(): void;
  setFocus(id: string): void;
  openTerminal(): void;
  /** The ↗ button: opens whatever the focused pill points at. */
  openTarget(): void;
  openUrl(url: string): void;
  /** allow / deny, or a plan's choice: auto mode, manual, or change it in the terminal. */
  decide(d: Decision): void;
  /** Answers the question Claude Code asked: question text → chosen label(s). */
  answer(answers: Record<string, string | string[]>): void;
  /** Takes the question card down; Claude Code asks in the terminal instead. */
  answerInTerminal(): void;
  toggleSound(): void;
  setVolume(v: number): void;
  setAutoClose(seconds: number): void;
  openSettingsWindow(): void;
  blip(): void;
}

export interface ViewHost {
  el: HTMLElement;
  sync(): void;
  /** Called when the view becomes active, for views with a text field. */
  focus?(): void;
  /** Called every frame while the view is on screen. */
  tick?(nowMs: number): void;
}

// ── Shared pieces ─────────────────────────────────────────────────────────────

function card(wash: Wash, ...children: (Node | string)[]): HTMLElement {
  const el = h("div", { class: wash ? "card wash" : "card" }, ...children);
  if (wash) el.style.setProperty("--wash", washRGBA(wash));
  return el;
}

function btn(
  label: string,
  kind: "primary" | "secondary",
  onClick: () => void,
  kbd?: string,
): HTMLElement {
  return h(
    "button",
    { class: `btn ${kind}`, onclick: onClick },
    h("span", { text: label }),
    kbd ? h("span", { class: "kbd", text: kbd }) : null,
  );
}

/** AgentWho — coloured dot + task name + grey label. */
function agentWho(task: AgentTask | null, label: string): HTMLElement {
  const row = h("div", { class: "who-row" });
  if (task) {
    row.append(dot(task.color, 8), h("span", { class: "n", style: `color:${task.color}`, text: task.name }));
  }
  row.append(h("span", { text: label }));
  return row;
}

function stack(padLeft: number, padRight: number, ...children: Node[]): HTMLElement {
  const el = h("div", { class: "stack" }, ...children);
  el.style.padding = `4px ${padRight}px 4px ${padLeft}px`;
  return el;
}

// ── Header ────────────────────────────────────────────────────────────────────

export function buildHeader(actions: ViewActions): ViewHost {
  const tabHome = h("button", { class: "tab", title: "Overview", onclick: () => go("overview") }, svg(ICONS.house, 13));
  const tabChat = h("button", { class: "tab", title: "Ask", onclick: () => go("prompt") }, svg(ICONS.bubble, 13));
  const tabDrop = h("button", { class: "tab", title: "Drop", onclick: () => go("upload") }, svg(ICONS.plus, 13));

  const gearBtn = h("button", { title: "Settings", onclick: () => go("settings") }, svg(ICONS.gear, 14));
  const soundBtn = h("button", { title: "Mute", onclick: () => actions.toggleSound() }, svg(ICONS.speakerOn, 14));
  // Focus mode: 25 minutes on, 5 off, until pressed again (island/focus.ts).
  const focusBtn = h("button", { onclick: () => { actions.blip(); Focus.toggle(); } }, svg(ICONS.timer, 14));
  const closeBtn = h("button", { title: "Küçült", onclick: () => actions.collapse() }, svg(ICONS.xmark, 12));

  function go(v: IslandViewName) {
    actions.blip();
    actions.setView(v);
  }

  const el = h(
    "div",
    { id: "header" },
    h("div", { class: "tabs" }, tabHome, tabChat, tabDrop),
    h("div", { class: "header-actions" }, focusBtn, gearBtn, soundBtn, closeBtn),
  );

  return {
    el,
    sync() {
      const v = State.view;
      tabHome.classList.toggle("on", v === "overview" || v === "empty" || v === "code");
      tabChat.classList.toggle("on", v === "prompt");
      tabDrop.classList.toggle("on", v === "upload");
      gearBtn.classList.toggle("on", v === "settings");
      focusBtn.classList.toggle("on", Focus.phase !== "off");
      focusBtn.title = Focus.phase === "off"
        ? tx("focusStart")
        : tx("focusStop");
      clear(gearBtn);
      gearBtn.append(svg(v === "settings" ? ICONS.gearFill : ICONS.gear, 14));
      clear(soundBtn);
      soundBtn.append(svg(State.settings.soundEnabled ? ICONS.speakerOn : ICONS.speakerOff, 14));
      el.style.opacity = v === "confused" ? "0" : "1";
    },
  };
}

// ── Overview ──────────────────────────────────────────────────────────────────

function buildOverview(actions: ViewActions): ViewHost {
  const ticker = new Ticker();
  const who = h("div", { class: "who" });
  const tickerBody = h("div", { class: "card-body" }, who, ticker.el);
  const leftBody = h("div", { class: "left-body" });
  const jump = h(
    "button",
    {
      class: "icon-btn jump",
      title: "Open",
      onclick: () => {
        // On the games pill the arrow swaps the other pills for the full library, and back.
        if (State.focusTask?.id === "integration_games") {
          wide = !wide;
          cardKey = "";
          State.notify();
        } else if (State.focusTask?.id === "integration_claude") {
          // On Kai's own pill it opens the live view of what Claude Code is editing.
          actions.blip();
          actions.setView("code");
        } else {
          actions.openTarget();
        }
      },
    },
    svg(ICONS.arrowUpRight, 8),
  );
  const left = card(null, leftBody, jump);
  const pills = h("div", { class: "pills" });
  const right = card(null, pills);

  const el = h("div", { class: "view overview" },
    h("div", { class: "left" }, left),
    h("div", { class: "right" }, right),
  );

  let pillIds = "";
  let wide = false;
  let detailOpen = false;
  let lastFocus: string | null = null;
  let mode: "ticker" | "card" | null = null;
  let cardKey = "";

  const hooks: IntegrationCardHooks = {
    get wide() {
      return wide;
    },
    get detailOpen() {
      return detailOpen;
    },
    openDetail() {
      detailOpen = true;
      cardKey = "";
      State.notify();
    },
    closeDetail() {
      detailOpen = false;
      cardKey = "";
      State.notify();
    },
    openSettings: () => openHostSettings(),
  };

  return {
    el,
    tick(nowMs: number) {
      if (mode === "ticker") ticker.tick(nowMs);
    },
    sync() {
      const task = State.focusTask;
      if (task?.id !== lastFocus) {
        lastFocus = task?.id ?? null;
        wide = false;
        detailOpen = false;
        cardKey = "";
        mode = null;
      }

      // VS Code with a live Claude Code session keeps the ticker; every other
      // pill shows its own card, exactly like IntegrationCardView.
      const sessionActive =
        task?.id === "integration_claude" && (task.state !== "idle" || task.steps.length > 0);

      if (task && sessionActive) {
        if (mode !== "ticker") {
          clear(leftBody);
          leftBody.append(tickerBody);
          mode = "ticker";
          cardKey = "";
        }
        clear(who);
        who.append(
          dot(task.color, 7),
          h("span", { class: "name", style: `color:${task.color}`, text: task.name }),
          h("span", { class: "tool", text: task.source === "claudeCode" ? "Claude Code" : "n8n" }),
        );
        // How much of the plan is used, at a glance while Claude works.
        const chip = task.id === "integration_claude" ? usageChip(State.usage) : "";
        if (chip) {
          const pct = usagePct(State.usage);
          who.append(h("span", { class: "usage-chip", style: pct != null ? `color:${usageColor(pct)}` : "", text: chip }));
        }
        // What Claude does after this turn, typed while it works.
        if (task.id === "integration_claude") {
          who.append(h("button", {
            class: "queue-chip",
            text: Queue.items.length ? `${tx("queue")} ${Queue.items.length}` : `+ ${tx("queue")}`,
            onclick: () => Queue.open(),
          }));
        }
        if (task.steps.length > 1) {
          who.append(h("span", {
            class: "count",
            // Past the twentieth step the list is a window on the session: show the real count.
            text: (task.stepSeq ?? 0) >= task.steps.length
              ? `${(task.stepSeq ?? 0) + 1}`
              : `${Math.min(task.stepIndex + 1, task.steps.length)}/${task.steps.length}`,
          }));
        }
        ticker.sync(task);
      } else if (task) {
        const info = State.integrations[task.id];
        const key = [
          task.id, detailOpen, wide, task.state, task.steps.join("|"),
          info?.loaded, info?.error, info?.configured, State.settings.hooksInstalled, tx("hooksOn"),
          State.integrations[task.id]?.configured,
          JSON.stringify(info?.data ?? {}),
          task.id === "integration_claude" ? JSON.stringify(State.usage) + Queue.items.length : "",
        ].join("~");
        if (key !== cardKey) {
          cardKey = key;
          mode = "card";
          clear(leftBody);
          leftBody.append(renderIntegrationCard(task, hooks));
        }
      }

      jump.style.display = detailOpen ? "none" : "";
      el.classList.toggle("wide", wide);
      jump.style.transform = wide ? "rotate(180deg)" : "";

      const others = State.otherTasks.slice(0, 4);
      const pillKey = others.map((t) => `${t.id}:${t.pillBadge ?? ""}`).join("|");
      if (pillKey !== pillIds) {
        pillIds = pillKey;
        clear(pills);
        for (const t of others) pills.append(buildPill(t, actions));
        pruneMiniBots();
      }
    },
  };
}

function buildPill(task: AgentTask, actions: ViewActions): HTMLElement {
  const label = pillName(task.id, task.name);
  const canvas = createMiniBot(task, 24);
  const pill = h(
    "div",
    { class: "pill", onclick: () => actions.setFocus(task.id) },
    canvas,
    h("span", { class: "lbl", text: label }),
  );
  pill.style.borderColor = `${task.color}24`;
  pill.addEventListener("mouseenter", () => {
    pill.style.background = `${task.color}2e`;
    pill.style.borderColor = `${task.color}8c`;
    pill.style.boxShadow = `0 2px 10px ${task.color}59`;
    (pill.querySelector(".lbl") as HTMLElement).style.color = lighten(task.color, 0.3);
  });
  pill.addEventListener("mouseleave", () => {
    pill.style.background = "";
    pill.style.borderColor = `${task.color}24`;
    pill.style.boxShadow = "";
    (pill.querySelector(".lbl") as HTMLElement).style.color = "";
  });

  if (task.pillBadge) {
    const colors = { approval: "#F5A524", finished: "#22C55E", error: "#F4505E" } as const;
    const icons = { approval: ICONS.bang, finished: ICONS.check, error: ICONS.xmark } as const;
    const inner = h("i", { style: `background:${colors[task.pillBadge]}` }, svg(icons[task.pillBadge], 6, { stroke: task.pillBadge === "finished" ? 3 : 0 }));
    const badge = h("div", { class: "pill-badge" }, inner);
    badge.style.boxShadow = `0 0 4px ${colors[task.pillBadge]}99`;
    pill.append(badge);
  }
  return pill;
}

function lighten(hex: string, amount: number): string {
  const v = parseInt(hex.replace("#", ""), 16);
  const c = [(v >> 16) & 255, (v >> 8) & 255, v & 255].map((x) =>
    Math.min(255, Math.round(x + amount * 255)),
  );
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

// ── Empty ─────────────────────────────────────────────────────────────────────

function buildEmpty(actions: ViewActions): ViewHost {
  const body = h(
    "div",
    { class: "stack", style: "padding:0 18px 0 118px;flex-direction:row;align-items:center;gap:16px" },
    h(
      "div",
      { style: "display:flex;flex-direction:column;gap:5px" },
      h("div", { class: "title", text: "Nothing running right now." }),
      h("div", { class: "sub", text: "Drop a file or window, or ask me anything." }),
    ),
    h("div", { class: "grow" }),
    btn("Ask Claude", "primary", () => actions.setView("prompt")),
  );
  return { el: h("div", { class: "view" }, card(null, body)), sync() {} };
}

// ── Approval ──────────────────────────────────────────────────────────────────

function buildApproval(actions: ViewActions): ViewHost {
  const who = h("div");
  const code = h("div", { class: "code" });
  const row = h("div", { class: "actions" });
  const el = h("div", { class: "view" }, card("amber", stack(116, 16, who, code, row)));
  let rowKey = "";
  return {
    el,
    sync() {
      const plan = State.pendingApproval?.tool === "ExitPlanMode";
      clear(who);
      who.append(agentWho(State.focusTask, plan ? tx("planReady") : tx("needsPermission")));
      // The whole point of approving here rather than in the terminal: this line
      // is the command, the file path or the URL being authorised, not just the
      // name of the tool asking.
      code.textContent = State.pendingApproval?.command || State.pendingApproval?.tool || "…";
      // Two buttons, built once. Rebuilding them between a mouse-down and a
      // mouse-up would swallow the click, and there is nothing left to vary:
      // "Always" is gone until the remembered-rules list exists to back it.
      // Only the wording can change, when the language does.
      const always = !plan && Boolean(State.pendingApproval?.canAlways);
      const key = `${plan}:${always}:${tx("allow")}`;
      if (rowKey === key) return;
      rowKey = key;
      clear(row);
      if (plan) {
        // The terminal's own plan choices, not a tool permission.
        row.append(
          btn(tx("planChange"), "secondary", () => actions.decide("plan_change")),
          btn(tx("planAuto"), "primary", () => actions.decide("plan_auto")),
          btn(tx("planManual"), "secondary", () => actions.decide("plan_default")),
        );
        return;
      }
      row.append(
        btn(tx("deny"), "secondary", () => actions.decide("deny")),
        btn(tx("allow"), "primary", () => actions.decide("allow")),
      );
      // Only when Claude Code offered a rule to keep: then it stops asking for this.
      if (always) row.append(btn(tx("always"), "secondary", () => actions.decide("always")));
    },
  };
}

// ── Question ──────────────────────────────────────────────────────────────────

function buildQuestion(actions: ViewActions): ViewHost {
  const who = h("div");
  const title = h("div", { class: "title question-text" });
  const row = h("div", { class: "actions options" });
  const el = h("div", { class: "view" }, card("cyan", stack(116, 16, who, title, row)));

  // Where we are in the request on screen: which question, what is answered so
  // far, and what is ticked in a pick-several question.
  let requestId = "";
  let index = 0;
  let answers: Record<string, string | string[]> = {};
  let picked = new Set<string>();
  // The buttons are only rebuilt when what they show changes: rebuilding them
  // between a mouse-down and a mouse-up would swallow the click.
  let rowKey = "";

  const next = (question: string, answer: string | string[], total: number) => {
    answers[question] = answer;
    picked = new Set();
    index += 1;
    if (index >= total) actions.answer(answers);
    else State.notify();
  };

  return {
    el,
    sync() {
      const questions = State.pendingApproval?.questions;
      clear(who);

      // A question that arrived as a notification has nothing to pick from.
      if (!questions) {
        who.append(agentWho(State.focusTask, tx("asking")));
        title.textContent = State.focusTask?.steps.at(-1) ?? "";
        if (rowKey !== `terminal:${tx("inTerminal")}`) {
          rowKey = `terminal:${tx("inTerminal")}`;
          clear(row);
          row.append(h("div", { class: "sub", text: tx("inTerminal") }));
        }
        return;
      }

      if (State.pendingApproval!.requestId !== requestId) {
        requestId = State.pendingApproval!.requestId;
        index = 0;
        answers = {};
        picked = new Set();
      }
      const q = questions[Math.min(index, questions.length - 1)];
      who.append(agentWho(State.focusTask, questions.length > 1 ? `${tx("asking")} (${index + 1}/${questions.length})` : tx("asking")));
      title.textContent = q.question;
      title.title = q.question;

      const key = `${requestId}:${index}:${[...picked].join("|")}:${tx("inTerminal")}`;
      if (rowKey === key) return;
      rowKey = key;
      clear(row);
      for (const option of q.options) {
        const on = picked.has(option.label);
        const button = btn(option.label, on ? "primary" : "secondary", () => {
          if (!q.multiSelect) {
            next(q.question, option.label, questions.length);
            return;
          }
          if (on) picked.delete(option.label);
          else picked.add(option.label);
          State.notify();
        });
        if (option.description) button.title = option.description;
        row.append(button);
      }
      if (q.multiSelect) {
        const done = btn(tx("done"), "primary", () => {
          if (picked.size > 0) next(q.question, [...picked], questions.length);
        });
        if (picked.size === 0) done.classList.add("off");
        row.append(done);
      }
      row.append(
        h("button", {
          class: "link-btn",
          style: "color:#8e939c",
          text: tx("inTerminal"),
          onclick: () => actions.answerInTerminal(),
        }),
      );
    },
  };
}

// ── Error ─────────────────────────────────────────────────────────────────────

function buildError(actions: ViewActions): ViewHost {
  const who = h("div");
  const title = h("div", { class: "title", text: "Workflow stopped." });
  const detail = h("div", { class: "detail" });
  const row = h("div", { class: "actions" },
    btn("Retry", "primary", () => actions.setView(State.defaultView())),
    btn("Open in n8n", "secondary", () => actions.openUrl("")),
  );
  const el = h("div", { class: "view" }, card("red", stack(116, 16, who, title, detail, row)));
  return {
    el,
    sync() {
      const task = State.focusTask;
      clear(who);
      who.append(agentWho(task, task?.source === "n8n" ? "n8n" : "Claude Code"));
      title.textContent = task?.source === "n8n" ? "Workflow stopped." : "Session stopped on an error.";
      detail.textContent = task?.steps.at(-1) ?? "No detail available.";
    },
  };
}

// ── Finished ──────────────────────────────────────────────────────────────────

/**
 * The turn is over: which files it changed and by how much, the way a diff
 * summary reads (+added −removed), three at most. With no file touched, what
 * the agent said.
 */
function buildFinished(actions: ViewActions): ViewHost {
  const who = h("div");
  const files = h("div", { class: "done-files" });
  const title = h("div", { class: "title done-line" });
  const row = h("div", { class: "actions" });
  const el = h("div", { class: "view" }, card("green", stack(116, 16, who, files, title, row)));
  let rowKey = "";
  return {
    el,
    sync() {
      const task = State.focusTask;
      const isClaude = task?.id === "integration_claude";
      const list = isClaude ? [...Turn.files.values()] : [];
      const minutes = Math.max(1, Math.round((Date.now() - Turn.startedAt) / 60_000));
      const tr = turkish();
      const parts = [tr ? "bitirdi" : "finished"];
      if (list.length) parts.push(tr ? `${list.length} dosya` : `${list.length} file${list.length > 1 ? "s" : ""}`);
      if (isClaude) parts.push(tr ? `${minutes} dk` : `${minutes} min`);
      clear(who);
      who.append(agentWho(task, parts.join(" · ")));

      clear(files);
      for (const f of list.slice(0, 3)) {
        files.append(h("div", { class: "done-file", title: f.path },
          h("span", { class: "done-name", text: f.name }),
          f.added ? h("span", { class: "done-add", text: `+${f.added}` }) : null,
          f.removed ? h("span", { class: "done-del", text: `−${f.removed}` }) : null,
        ));
      }
      if (list.length > 3) files.append(h("div", { class: "done-more", text: tr ? `+${list.length - 3} dosya daha` : `+${list.length - 3} more` }));
      files.style.display = list.length ? "" : "none";

      // No file changed: what the agent said at the end of its turn.
      title.textContent = list.length ? "" : (task?.finalLine || (tr ? "İş bitti" : "Done"));
      title.style.display = list.length ? "none" : "";

      // The buttons are only rebuilt when they change: a rebuild between a
      // mouse-down and a mouse-up would swallow the click.
      const key = `${list.length > 0}:${tr}`;
      if (key === rowKey) return;
      rowKey = key;
      clear(row);
      row.append(
        list.length
          ? btn(tr ? "Değişikliklere bak" : "See the changes", "primary", () => actions.setView("code"))
          : btn(tr ? "Terminale git" : "Open terminal", "primary", () => actions.openTerminal()),
        btn(tr ? "Tamam" : "OK", "secondary", () => actions.collapse()),
      );
    },
  };
}

// ── Confused ──────────────────────────────────────────────────────────────────

function buildConfused(): ViewHost {
  const body = h(
    "div",
    { class: "stack", style: "padding:0 18px 0 128px" },
    h("div", { class: "title", text: "Too many hits at once." }),
    h("div", { class: "sub", text: "Give me a sec — back to work in three seconds." }),
  );
  return { el: h("div", { class: "view" }, card("pink", body)), sync() {} };
}

// ── Note ──────────────────────────────────────────────────────────────────────

function buildNote(): ViewHost {
  const title = h("div", { class: "title" });
  const el = h("div", { class: "view" }, card(null, h("div", { class: "stack", style: "padding:0 18px 0 98px" }, title)));
  return {
    el,
    sync() {
      title.textContent = State.noteMessage ?? "";
    },
  };
}

// ── In-island settings ────────────────────────────────────────────────────────

function buildSettings(actions: ViewActions): ViewHost {
  const soundSwitch = h("button", { class: "switch", onclick: () => actions.toggleSound() });
  const volume = h("input", {
    type: "range", min: "0", max: "0.2", step: "0.005",
    oninput: (e: Event) => actions.setVolume(Number((e.target as HTMLInputElement).value)),
  }) as HTMLInputElement;
  const autoLabel = h("span", {});
  const segButtons = [10, 15, 30].map((s) =>
    h("button", { onclick: () => actions.setAutoClose(s) }, `${s}s`),
  );
  const claudeBadge = h("span", { class: "status-badge" });
  const apiBadge = h("span", { class: "status-badge" });

  // Language, voice and listening belong to Kai itself, so they are saved by the host.
  const pick = (key: "language" | "voice" | "model") =>
    h("select", {
      class: "pref",
      onchange: (e: Event) => void setPref(key, (e.target as HTMLSelectElement).value),
    }) as HTMLSelectElement;
  const language = pick("language");
  const voice = pick("voice");
  const quality = pick("model");
  const micSwitch = h("button", {
    class: "switch",
    onclick: () => void setPref("mic", !(prefs()?.mic ?? false)),
  });
  const speakSwitch = h("button", {
    class: "switch",
    onclick: () => void setPref("speak", !(prefs()?.speak ?? false)),
  });
  const speakLabel = h("span", {});
  const accessory = h("select", {
    class: "pref",
    onchange: (e: Event) => void setPref("accessory", (e.target as HTMLSelectElement).value),
  }) as HTMLSelectElement;
  const accessoryLabel = h("span", {});
  const mascot = h("select", {
    class: "pref",
    onchange: (e: Event) => void setPref("mascot", (e.target as HTMLSelectElement).value),
  }) as HTMLSelectElement;
  const mascotLabel_ = h("span", {});
  const colorLabel = h("span", {});
  const swatches = BODY_COLORS.map((color) => h("button", {
    class: "swatch",
    style: `background:${color}`,
    onclick: () => void setPref("color", color),
  }));
  // Any other colour: a hue, at a strength the eyes stay readable on.
  const hue = h("input", {
    type: "range", class: "hue", min: "0", max: "359", step: "1",
    oninput: (e: Event) => setBodyColor(hueColor(Number((e.target as HTMLInputElement).value))),
    onchange: (e: Event) => void setPref("color", hueColor(Number((e.target as HTMLInputElement).value))),
  }) as HTMLInputElement;
  const city = h("input", {
    type: "text",
    class: "pref",
    spellcheck: "false",
    onchange: (e: Event) => void setPref("city", (e.target as HTMLInputElement).value),
    onkeydown: (e: Event) => {
      if ((e as KeyboardEvent).key === "Enter") (e.target as HTMLInputElement).blur();
      e.stopPropagation(); // typing must not reach the island's own shortcuts
    },
  }) as HTMLInputElement;
  const cityLabel = h("span", {});
  const startupSwitch = h("button", {
    class: "switch",
    onclick: () => void setPref("startup", !(prefs()?.startup ?? false)),
  });
  const startupLabel = h("span", {});
  const agentsLabel = h("span", {});
  const wardrobeButton = h("button", {
    class: "link-btn",
    style: "color:#35B8FF;font-size:11.5px",
    onclick: () => actions.setView("wardrobe"),
  });
  const agentChips = h("div", { class: "agent-chips" });
  const agentNote = h("div", { class: "agent-note" });
  const soundLabel = h("span", {});
  const languageLabel = h("span", {});
  const micLabel = h("span", {});
  const voiceLabel = h("span", {});
  const qualityLabel = h("span", {});
  const versionLabel = h("span", {class: "status-badge"});
  let updating = false;
  let checked = false;
  const updateButton = h("button", {
    class: "link-btn",
    style: "color:#35B8FF;font-size:11.5px",
    onclick: async () => {
      if (updating) return;
      if (prefs()?.updateAvailable) {
        updating = true;
        State.notify();
        await runUpdate("install");
      } else {
        await runUpdate("check");
        checked = true;
        State.notify();
      }
    },
  });
  const allSettings = h("button", {
    class: "link-btn",
    style: "color:#8e939c;font-size:11.5px",
    onclick: () => openHostSettings(),
  });

  /** Rebuilds a dropdown only when its choices change, so an open one is never yanked shut. */
  function fill(select: HTMLSelectElement, choices: [string, string][], value: string) {
    const key = choices.map(([label, id]) => `${id}=${label}`).join("|");
    if (select.dataset.key !== key) {
      select.dataset.key = key;
      clear(select);
      for (const [label, id] of choices) select.append(h("option", { value: id, text: label }));
    }
    if (select.value !== value) select.value = value;
  }

  let loadedAt = 0;

  const rows = h(
    "div",
    { class: "settings-rows" },
    // Version and update come first: at the bottom they slid out of sight as
    // the list grew, and nobody could reach the update button.
    h(
      "div",
      { class: "settings-row", style: "gap:14px" },
      claudeBadge,
      apiBadge,
      versionLabel,
      h("div", { class: "grow" }),
      updateButton,
      allSettings,
    ),
    h(
      "div",
      { class: "settings-row" },
      soundSwitch, soundLabel, volume,
      h("div", { class: "grow" }),
      svg(ICONS.timer, 12),
      autoLabel,
      h("div", { class: "seg" }, ...segButtons),
    ),
    h("div", { class: "settings-row" }, languageLabel, language, h("div", { class: "grow" }), speakLabel, speakSwitch, micLabel, micSwitch),
    h("div", { class: "settings-row" }, voiceLabel, voice, h("div", { class: "grow" }), qualityLabel, quality),
    h("div", { class: "settings-row" }, accessoryLabel, accessory, h("div", { class: "grow" }), cityLabel, city),
    h("div", { class: "settings-row" }, mascotLabel_, mascot, wardrobeButton, h("div", { class: "grow" }), startupLabel, startupSwitch),
    h("div", { class: "settings-row" }, colorLabel, ...swatches, hue),
    h("div", { class: "settings-row" }, agentsLabel, agentChips),
    agentNote,
  );

  const el = h("div", { class: "view" },
    card(null, h("div", { class: "stack", style: "padding:14px 16px 14px 84px" }, rows)));

  return {
    el,
    sync() {
      const s = State.settings;
      soundSwitch.classList.toggle("on", s.soundEnabled);
      volume.value = String(s.soundVolume);
      volume.style.opacity = s.soundEnabled ? "1" : "0.4";
      autoLabel.textContent = `${tx("autoClose")} · ${Math.round(s.autoCloseInterval)}s`;
      soundLabel.textContent = tx("sound");
      languageLabel.textContent = tx("language");
      micLabel.textContent = tx("mic");
      speakLabel.textContent = tx("speak");
      accessoryLabel.textContent = tx("accessory");
      mascotLabel_.textContent = tx("mascot");
      colorLabel.textContent = tx("color");
      swatches.forEach((b, i) => b.classList.toggle("on", BODY_COLORS[i] === bodyHex()));
      cityLabel.textContent = tx("city");
      startupLabel.textContent = tx("startup");
      agentsLabel.textContent = tx("agents");
      wardrobeButton.textContent = tx("wardrobe");
      voiceLabel.textContent = tx("voice");
      qualityLabel.textContent = tx("quality");
      allSettings.textContent = tx("allSettings");

      // The tray can change these too, so the view re-reads them while it is open.
      if (State.view === "settings" && performance.now() - loadedAt > 3000) {
        loadedAt = performance.now();
        void loadPrefs();
      }
      const p = prefs();
      if (p) {
        fill(language, p.languages.map(([code, name]) => [name, code]), p.language);
        fill(voice, p.voices, p.voice);
        fill(quality, p.models, p.model);
        micSwitch.classList.toggle("on", p.mic);
        speakSwitch.classList.toggle("on", p.speak);
        versionLabel.textContent = `Kai ${p.version}`;
        updateButton.textContent = updating
          ? tx("updating")
          : p.updateAvailable
            ? `${tx("update")} → ${p.updateLatest}`
            : checked && !p.updateError
              ? tx("upToDate")
              : tx("check");
        startupSwitch.classList.toggle("on", p.startup);
        // Only agents found on this computer, plus any already connected.
        const shown = (p.agents ?? []).filter((a) => a.present || a.installed);
        const agentKey = shown.map((a) => `${a.id}:${a.installed}`).join("|");
        if (agentChips.dataset.key !== agentKey) {
          agentChips.dataset.key = agentKey;
          clear(agentChips);
          for (const a of shown) {
            agentChips.append(h("button", {
              class: a.installed ? "agent-chip on" : "agent-chip",
              text: a.name,
              title: a.path,
              onclick: () => void setAgent(a.id, !a.installed),
            }));
          }
        }
        agentNote.textContent = p.agentNote ?? "";
        // Never overwrite the box while someone is typing in it.
        if (document.activeElement !== city && city.value !== p.city) city.value = p.city;
        fill(mascot, PICKABLE.map((kind) => [mascotLabel(kind), kind]), parseMascot(p.mascot));
        fill(
          accessory,
          [
            [tx("accNone"), "none"], [tx("accWitch"), "witch"], [tx("accPumpkin"), "pumpkin"],
            [tx("accBat"), "bat"], [tx("accHorns"), "horns"], [tx("accVampire"), "vampire"],
          ],
          p.accessory,
        );
      }
      segButtons.forEach((b, i) => b.classList.toggle("on", s.autoCloseInterval === [10, 15, 30][i]));
      clear(claudeBadge);
      claudeBadge.append(
        dot(s.hooksInstalled ? "#22C55E" : "#F4505E", 6),
        h("span", { text: "Claude Code" }),
      );
      clear(apiBadge);
      apiBadge.append(dot(prefs()?.api ? "#22C55E" : "#F4505E", 6), h("span", { text: "API" }));
    },
  };
}

// ── Placeholders filled in later stages ───────────────────────────────────────

function buildPlaceholder(title: string, sub: string): ViewHost {
  const body = h(
    "div",
    { class: "stack", style: "padding:0 18px 0 118px" },
    h("div", { class: "title", text: title }),
    h("div", { class: "sub", text: sub }),
  );
  return { el: h("div", { class: "view" }, card(null, body)), sync() {} };
}

// ── Registry ──────────────────────────────────────────────────────────────────

export function buildViews(
  actions: ViewActions,
  onChatHeightChange: () => void,
): Map<IslandViewName, ViewHost> {
  const map = new Map<IslandViewName, ViewHost>();
  map.set("overview", buildOverview(actions));
  map.set("empty", buildEmpty(actions));
  map.set("approval", buildApproval(actions));
  map.set("question", buildQuestion(actions));
  map.set("error", buildError(actions));
  map.set("finished", buildFinished(actions));
  map.set("confused", buildConfused());
  map.set("note", buildNote());
  map.set("settings", buildSettings(actions));
  map.set("wardrobe", buildWardrobe());
  map.set("update", buildUpdate(() => actions.collapse(), updateLater));
  map.set("code", buildCode(() => actions.setView("overview")));
  map.set("prompt", buildPrompt(onChatHeightChange));
  map.set("queue", buildQueue(() => actions.setView(State.defaultView())));
  Queue.open = () => actions.setView("queue");
  map.set("summary", buildSummary(() => actions.collapse()));
  map.set("upload", buildUpload());
  map.set("uploading", buildUploading());
  map.set("choose", buildChoose(actions));
  // Not in the Windows v1: sending a file by email, window attach + web result.
  map.set("mail", buildPlaceholder("Sending by email isn't in this version.", ""));
  map.set("searching", buildPlaceholder("Claude is searching…", ""));
  map.set("result", buildPlaceholder("Result", ""));
  return map;
}
