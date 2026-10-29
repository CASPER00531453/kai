// Integration cards shown in the overview's left card — DOM ports of
// IntegrationCardView and friends from IslandViewContent.swift.
//
// Cal.com is the one simplification: macOS shows a three-level calendar
// (month → day → booking); here it is the list of upcoming bookings.

import { h, svg, clear, dot } from "./dom";
import { usageColor, usageRows } from "../core/usage";
import { ICONS } from "./icons";
import { State, type AgentTask } from "../core/state";
import { Bridge } from "../core/bridge";
import { Queue } from "./queue";
import { pillName, turkish, tx } from "../core/prefs";

/** Same shape as the Swift `timeAgo` computed properties. */
export function timeAgo(value: unknown): string {
  const date = typeof value === "number" ? new Date(value) : new Date(String(value));
  const diff = (Date.now() - date.getTime()) / 1000;
  if (!Number.isFinite(diff)) return "";
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function header(color: string, name: string, kind: string, extra?: Node, tint = false): HTMLElement {
  const title = h("b", { text: name });
  if (tint) title.style.color = color;
  const row = h("div", { class: "int-head" }, dot(color, 7), title, h("span", { text: kind }));
  if (extra) row.append(extra);
  return row;
}

/** Highlighted first row + plain rows, the layout every list card shares. */
function listRow(accent: string, first: boolean, ...children: Node[]): HTMLElement {
  const row = h("div", { class: first ? "int-row first" : "int-row" }, dot(accent, 5), ...children);
  if (first) row.style.background = `${accent}14`;
  return row;
}

function get(id: string): Record<string, unknown> {
  return (State.integrations[id]?.data ?? {}) as Record<string, unknown>;
}

function arr(id: string, key: string): Record<string, unknown>[] {
  const v = get(id)[key];
  return Array.isArray(v) ? (v as Record<string, unknown>[]) : [];
}

// ── Not configured / idle ─────────────────────────────────────────────────────

const OPEN_URLS: Record<string, string> = {
  integration_resend: "https://resend.com/emails",
  integration_vercel: "https://vercel.com/dashboard",
  integration_github: "https://github.com",
  integration_stripe: "https://dashboard.stripe.com/payments",
  integration_notion: "https://notion.so",
  integration_calcom: "https://app.cal.com/bookings",
};

function idleCard(task: AgentTask, openSettings: () => void): HTMLElement {
  const info = State.integrations[task.id];
  const configured = info?.configured ?? false;
  const error = info?.error ?? null;
  // The Claude Code pill is about hooks, not a key — the macOS wording would be
  // misleading here.
  const isKai = task.id === "integration_claude";
  // Kai's own pill is about the Claude Code hooks, which the host reports.
  const hooked = isKai && State.settings.hooksInstalled;
  const missing = isKai ? tx("hooksOff") : task.id === "integration_weather" ? tx("noCity") : tx("keyMissing");
  const label = hooked ? tx("hooksOn") : error ?? (configured ? tx("loading") : missing);
  const statusColor = hooked ? "#22C55E" : error || !configured ? "#F4505E" : "#22C55E";

  const actions = h("div", { class: "int-actions" });
  if (isKai) {
    // Nothing to open: Claude Code sessions show up here on their own.
  } else if (task.id === "integration_n8n") {
    actions.append(
      h("button", {
        class: "link-btn",
        style: `color:${task.color}d9`,
        text: "Open n8n",
        onclick: () => void Bridge.openN8n(),
      }),
    );
  } else if (OPEN_URLS[task.id]) {
    actions.append(
      h("button", {
        class: "link-btn",
        style: `color:${task.color}d9`,
        text: `${task.name} · ${tx("open")}`,
        onclick: () => void Bridge.openUrl(OPEN_URLS[task.id]),
      }),
    );
  }
  if (isKai) {
    actions.append(
      h("button", {
        class: "link-btn",
        style: `color:${task.color}d9`,
        text: Queue.items.length ? `${tx("queue")} (${Queue.items.length})` : tx("queue"),
        onclick: () => Queue.open(),
      }),
      h("button", { class: "link-btn", style: "color:#8e939c", text: tx("allSettings"), onclick: openSettings }),
    );
  } else if (configured) {
    actions.append(
      h("button", {
        class: "link-btn",
        style: `color:${task.color}d9`,
        text: tx("refresh"),
        onclick: () => void Bridge.refreshIntegration(task.id),
      }),
    );
  } else {
    actions.append(
      h("button", { class: "link-btn", style: "color:#8e939c", text: tx("allSettings"), onclick: openSettings }),
    );
  }

  // Kai's pill also tells how much of the Claude plan is used.
  const usage = isKai
    ? usageRows(State.usage).map(([name, detail, pct]) => h("div", { class: "usage-row" },
      h("div", { class: "usage-text" }, h("span", { text: name }), h("span", { class: "usage-detail", text: detail })),
      pct == null ? null : h("div", { class: "usage-bar" },
        h("div", { class: "usage-fill", style: `width:${Math.max(3, pct)}%;background:${usageColor(pct)}` }))))
    : [];
  return h(
    "div",
    { class: "int-card" },
    header(task.color, pillName(task.id, task.name), isKai ? "Claude Code" : "", undefined, isKai),
    h("div", { class: "int-status" }, dot(statusColor, 5), h("span", { text: label })),
    ...usage,
    actions,
  );
}

// ── Vercel ────────────────────────────────────────────────────────────────────

function vercelCard(onDetail: () => void): HTMLElement {
  const deployments = arr("integration_vercel", "deployments");
  const rows = h("div", { class: "int-rows" });
  deployments.slice(0, 3).forEach((d, i) => {
    const accent = d.state === "READY" ? "#22C55E" : "#F4505E";
    const name = h("span", { class: "int-name", text: String(d.projectName ?? "") });
    const ago = h("span", { class: "int-ago", text: timeAgo(d.createdAt) });
    if (i === 0) {
      const more = h(
        "button",
        { class: "int-more", title: "Details", onclick: onDetail },
        svg(ICONS.ellipsis, 8),
      );
      rows.append(listRow(accent, true, name, ago, more));
    } else {
      rows.append(listRow(accent, false, name, ago));
    }
  });
  return h("div", { class: "int-card" }, header("#7C5CFF", "Vercel", tx("deployments")), rows);
}

function vercelDetail(onBack: () => void): HTMLElement {
  const d = arr("integration_vercel", "deployments")[0] ?? {};
  const success = d.state === "READY";
  const accent = success ? "#22C55E" : "#F4505E";
  const status = success ? "Ready" : d.state === "CANCELED" ? "Canceled" : "Error";
  const body = h("div", { class: "int-detail-body" });
  if (d.commitMessage) body.append(h("div", { class: "int-commit", text: String(d.commitMessage) }));
  const meta = h("div", { class: "int-meta" });
  if (d.branch) meta.append(h("span", { text: String(d.branch) }));
  meta.append(h("span", { text: `${timeAgo(d.createdAt)} ago` }));
  body.append(meta);
  if (d.url) {
    body.append(
      h("button", {
        class: "int-link",
        text: String(d.url),
        onclick: () => void Bridge.openUrl(`https://${d.url}`),
      }),
    );
  }
  return h(
    "div",
    { class: "int-card detail" },
    h(
      "div",
      { class: "int-detail-head" },
      h("button", { class: "int-back", onclick: onBack }, svg(ICONS.chevronLeft, 10, { stroke: 2.4 })),
      dot(accent, 6),
      h("b", { text: String(d.projectName ?? "Deployment") }),
      h("span", { class: "int-badge", style: `color:${accent};background:${accent}24`, text: status }),
    ),
    body,
  );
}

// ── Resend ────────────────────────────────────────────────────────────────────

function resendCard(): HTMLElement {
  const emails = arr("integration_resend", "emails");
  const total = get("integration_resend").total;
  const extra =
    total != null
      ? h("span", { class: "int-total" }, h("i", { class: "pulse" }), h("span", { text: String(total) }))
      : undefined;
  const rows = h("div", { class: "int-rows" });
  emails.slice(0, 3).forEach((e, i) => {
    const delivered = e.lastEvent === "delivered";
    const accent = delivered ? "#22C55E" : "#F4505E";
    const to = Array.isArray(e.to) ? String(e.to[0] ?? "?") : "?";
    const short = to.split("@")[0];
    const cells: Node[] = [
      h("span", { class: "int-name", text: short }),
      h("span", { class: "int-ago", text: timeAgo(e.createdAt) }),
    ];
    if (i === 0 && e.subject) cells.push(h("span", { class: "int-sub", text: String(e.subject) }));
    rows.append(listRow(accent, i === 0, ...cells));
  });
  return h("div", { class: "int-card" }, header("#22C55E", "Resend", "Emails", extra), rows);
}

// ── GitHub ────────────────────────────────────────────────────────────────────

function statRow(icon: string, color: string, label: string, value: string): HTMLElement {
  return h(
    "div",
    { class: "int-stat" },
    h("i", { class: "int-stat-icon", style: `color:${color}` }, svg(icon, 10)),
    h("span", { class: "int-stat-label", text: label }),
    h("span", { class: "int-stat-value", text: value }),
  );
}

function githubCard(): HTMLElement {
  const d = get("integration_github");
  const stars = Number(d.totalStars ?? 0);
  const repos = Number(d.totalRepos ?? 0);
  const fmt = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
  return h(
    "div",
    { class: "int-card" },
    header("#F4505E", String(d.login || "GitHub"), tx("overview")),
    h(
      "div",
      { class: "int-stats" },
      statRow(ICONS.star, "#F5A524", tx("stars"), fmt(stars)),
      statRow(ICONS.stack, "#6B7079", tx("repos"), String(repos)),
    ),
  );
}

// ── Spotify ───────────────────────────────────────────────────────────────────

const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

function spotifyCard(): HTMLElement {
  const d = get("integration_spotify");
  const title = String(d.title ?? "");
  const artist = String(d.artist ?? "");
  const song = [artist, title].filter(Boolean).join(" — ");
  const green = "#1DB954";
  const position = Number(d.position ?? 0);
  const duration = Number(d.duration ?? 0);
  // The card is redrawn as the song moves on, so these act on press: a click
  // that straddles a redraw would be lost.
  const control = (icon: string, op: string) =>
    h("button", { class: "media-btn", onmousedown: () => Bridge.mediaDo(op) }, svg(icon, 11));
  const link = (text: string, op: string, color: string, icon?: string) => {
    const el = h("button", { class: "link-btn", style: `color:${color}`, onmousedown: () => Bridge.mediaDo(op) });
    if (icon) el.append(svg(icon, 10), " ");
    el.append(text);
    return el;
  };
  const actions = h(
    "div",
    { class: "int-actions" },
    control(ICONS.prev, "prev"),
    control(d.playing ? ICONS.pause : ICONS.play, "toggle"),
    control(ICONS.next, "next"),
    h("div", { class: "grow" }),
  );
  if (song) actions.append(link(tx("favSave"), "fav_save", "#F5A524", ICONS.star));
  if (d.favorite) actions.append(link(tx("favPlay"), "fav_play", `${green}d9`));
  const card = h(
    "div",
    { class: "int-card" },
    header(green, "Spotify", song ? (d.playing ? tx("nowPlaying") : tx("paused")) : ""),
    h("div", { class: "int-status" }, h("span", { class: "int-name", style: "color:#e8e9ec", text: song || tx("nothingPlaying") })),
  );
  if (song && duration > 0) {
    const fill = h("i", { style: `width:${Math.min(100, (position / duration) * 100)}%;background:${green}` });
    card.append(
      h(
        "div",
        { class: "int-status", style: "padding-right:12px" },
        h("span", { class: "media-time", text: clock(position) }),
        h("div", { class: "media-bar" }, fill),
        h("span", { class: "media-time", text: clock(duration) }),
      ),
    );
  }
  card.append(actions);
  return card;
}

// ── Steam games ───────────────────────────────────────────────────────────────

function gamesCard(task: AgentTask, wide: boolean): HTMLElement {
  const all = arr("integration_games", "games");
  const total = Number(get("integration_games").total ?? all.length);
  // Three most recent by default; the arrow opens the whole library as a scrolling list.
  const games = wide ? all : all.slice(0, 3);
  const rows = h("div", { class: wide ? "int-rows scroll" : "int-rows" });
  if (games.length === 0) rows.append(h("div", { class: "int-empty", text: tx("noGames") }));
  games.forEach((g, i) => {
    const row = listRow(
      task.color,
      i === 0,
      h("span", { class: "int-name", text: String(g.name ?? "") }),
      h("span", { class: "int-ago", text: Number(g.lastPlayed) > 0 ? timeAgo(g.lastPlayed) : "" }),
      h("div", { class: "grow" }),
      h("span", { class: "int-ago", text: wide ? String(g.store ?? "") : "" }),
    );
    row.classList.add("game");
    row.addEventListener("click", () => Bridge.launchGame(String(g.id ?? "")));
    rows.append(row);
  });
  const kind = wide ? tx("allGames") : `${total} ${tx("installed")}`;
  return h("div", { class: "int-card" }, header(task.color, tx("games"), kind), rows);
}

// ── This computer ─────────────────────────────────────────────────────────────

function meter(color: string, label: string, percent: number, value: string): HTMLElement {
  // Past 85 the bar turns red: that is when a game starts to stutter.
  const shade = percent >= 85 ? "#F4505E" : color;
  return h(
    "div",
    { class: "int-stat" },
    h("span", { class: "int-stat-label", style: "width:58px", text: label }),
    h("div", { class: "media-bar" }, h("i", { style: `width:${Math.max(0, Math.min(100, percent))}%;background:${shade}` })),
    h("span", { class: "int-stat-value", style: "margin-left:0;white-space:nowrap", text: value }),
  );
}

function systemCard(task: AgentTask): HTMLElement {
  const d = get("integration_system");
  const stats = h(
    "div",
    { class: "int-stats" },
    meter(task.color, tx("cpu"), Number(d.cpu ?? 0), `%${Number(d.cpu ?? 0)}`),
    meter(task.color, tx("ram"), Number(d.ram ?? 0), `${d.ramUsed ?? 0} / ${d.ramTotal ?? 0} GB`),
  );
  if (d.gpuTemp != null) {
    // 90 °C is where a graphics card is running hot, so that is a full bar.
    stats.append(meter(task.color, tx("gpu"), (Number(d.gpuTemp) / 90) * 85, `${d.gpuTemp}°C · %${d.gpuLoad ?? 0}`));
  }
  return h("div", { class: "int-card" }, header(task.color, tx("system"), String(d.gpuName ?? "")), stats);
}

// ── Weather ───────────────────────────────────────────────────────────────────

function weatherCard(task: AgentTask): HTMLElement {
  const d = get("integration_weather");
  const today = new Date().toLocaleDateString(turkish() ? "tr-TR" : "en-GB", { weekday: "long", day: "numeric", month: "long" });
  return h(
    "div",
    { class: "int-card" },
    header(task.color, String(d.city ?? tx("weather")), today),
    h("div", { class: "int-balance" }, h("span", { text: `${d.temp ?? 0}°` }), h("i", { text: String(d.sky ?? "") })),
    h(
      "div",
      { class: "int-status" },
      h("span", { text: `${tx("feels")} ${d.feels ?? 0}° · ${d.low ?? 0}° / ${d.high ?? 0}° · ${tx("wind")} ${d.wind ?? 0} km/h` }),
    ),
  );
}

// ── Stripe ────────────────────────────────────────────────────────────────────

function stripeCard(): HTMLElement {
  const d = get("integration_stripe");
  const balance = (Number(d.balance ?? 0) / 100).toFixed(2);
  const currency = String(d.currency ?? "eur").toUpperCase();
  const rows = h("div", { class: "int-rows tight" });
  for (const p of arr("integration_stripe", "payments")) {
    const success = p.status === "succeeded";
    const accent = success ? "#22C55E" : "#F4505E";
    rows.append(
      h(
        "div",
        { class: "int-row" },
        dot(accent, 5),
        h("span", { class: "int-name", text: String(p.description ?? "Payment") }),
        h("span", {
          class: "int-amount",
          style: "color:#22c55e",
          text: `+${(Number(p.amount ?? 0) / 100).toFixed(2)}`,
        }),
        h("span", { class: "int-ago", text: timeAgo(p.createdAt) }),
      ),
    );
  }
  return h(
    "div",
    { class: "int-card" },
    header("#0570DE", "Stripe", tx("payments")),
    h("div", { class: "int-balance" }, h("span", { text: balance }), h("i", { text: currency })),
    rows,
  );
}

// ── Notion ────────────────────────────────────────────────────────────────────

function notionCard(): HTMLElement {
  const rows = h("div", { class: "int-rows tight" });
  for (const p of arr("integration_notion", "pages").slice(0, 3)) {
    rows.append(
      h(
        "button",
        {
          class: "int-page",
          onclick: () => {
            if (typeof p.url === "string") void Bridge.openUrl(p.url);
          },
        },
        p.emoji
          ? h("span", { class: "int-emoji", text: String(p.emoji) })
          : h("i", { class: "int-emoji" }, svg(ICONS.doc, 9)),
        h("span", { class: "int-name", text: String(p.title ?? "Untitled") }),
        h("span", { class: "int-ago", text: timeAgo(p.lastEditedAt) }),
      ),
    );
  }
  return h("div", { class: "int-card" }, header("#E8E8E8", "Notion", "Recent"), rows);
}

// ── Cal.com ───────────────────────────────────────────────────────────────────

function calcomCard(): HTMLElement {
  const bookings = arr("integration_calcom", "bookings")
    .slice()
    .sort((a, b) => new Date(String(a.start)).getTime() - new Date(String(b.start)).getTime());
  const rows = h("div", { class: "int-rows tight" });
  if (bookings.length === 0) {
    rows.append(h("div", { class: "int-empty", text: "No calls scheduled" }));
  }
  for (const b of bookings.slice(0, 3)) {
    const when = new Date(String(b.start));
    const day = when.toLocaleDateString(undefined, { day: "2-digit", month: "2-digit" });
    const time = when.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    rows.append(
      h(
        "div",
        { class: "int-row" },
        dot("#C9956A", 4),
        h("span", { class: "int-time", text: `${day} ${time}` }),
        h("span", { class: "int-name", text: String(b.title ?? "Meeting") }),
      ),
    );
  }
  return h("div", { class: "int-card" }, header("#C9956A", "Cal.com", "Schedule"), rows);
}

// ── n8n ───────────────────────────────────────────────────────────────────────

function n8nCard(task: AgentTask, onDetail: () => void, openSettings: () => void): HTMLElement {
  const hasActivity = task.steps.length > 0 && (task.state === "finished" || task.state === "error");
  if (!hasActivity) return idleCard(task, openSettings);
  const success = task.state === "finished";
  const accent = success ? "#22C55E" : "#F4505E";
  return h(
    "div",
    { class: "int-card" },
    header("#F29B38", "n8n", "Workflow"),
    h(
      "div",
      { class: "int-actions" },
      h(
        "button",
        {
          class: "int-pill",
          style: `background:${accent}1a;border-color:${accent}38`,
          onclick: onDetail,
        },
        dot(accent, 5),
        h("span", { class: "int-name", text: task.steps[0] ?? "Workflow" }),
        svg(ICONS.ellipsis, 8),
      ),
    ),
  );
}

function n8nDetail(task: AgentTask, onBack: () => void): HTMLElement {
  const success = task.state === "finished";
  const accent = success ? "#22C55E" : "#F4505E";
  const detail = task.steps[1];
  return h(
    "div",
    { class: "int-card detail" },
    h(
      "div",
      { class: "int-detail-head" },
      h("button", { class: "int-back", onclick: onBack }, svg(ICONS.chevronLeft, 10, { stroke: 2.4 })),
      dot(accent, 6),
      h("b", { text: task.steps[0] ?? "Workflow" }),
      h("span", {
        class: "int-badge",
        style: `color:${accent};background:${accent}24`,
        text: success ? "Success" : "Failed",
      }),
    ),
    detail
      ? h("pre", { class: "int-detail-text", text: detail })
      : h("div", {
          class: "int-status",
          text: success ? "Completed successfully." : "No error details available.",
        }),
  );
}

// ── Dispatch ──────────────────────────────────────────────────────────────────

export interface IntegrationCardHooks {
  /** The card has the whole island to itself (the games list). */
  wide: boolean;
  detailOpen: boolean;
  openDetail(): void;
  closeDetail(): void;
  openSettings(): void;
}

/** True when this integration has data worth showing instead of the idle card. */
export function hasIntegrationData(id: string): boolean {
  const info = State.integrations[id];
  if (!info || info.error) return false;
  switch (id) {
    case "integration_vercel":
      return arr(id, "deployments").length > 0;
    case "integration_resend":
      return arr(id, "emails").length > 0;
    case "integration_github":
      return get(id).totalRepos != null;
    case "integration_stripe":
    case "integration_spotify":
    case "integration_games":
    case "integration_system":
    case "integration_weather":
      return info.loaded;
    case "integration_notion":
      return arr(id, "pages").length > 0;
    case "integration_calcom":
      return info.loaded;
    default:
      return false;
  }
}

export function renderIntegrationCard(task: AgentTask, hooks: IntegrationCardHooks): HTMLElement {
  if (task.id === "integration_n8n") {
    const hasActivity = task.steps.length > 0 && (task.state === "finished" || task.state === "error");
    return hooks.detailOpen && hasActivity
      ? n8nDetail(task, hooks.closeDetail)
      : n8nCard(task, hooks.openDetail, hooks.openSettings);
  }
  if (task.id === "integration_vercel" && hasIntegrationData(task.id)) {
    return hooks.detailOpen ? vercelDetail(hooks.closeDetail) : vercelCard(hooks.openDetail);
  }
  if (!hasIntegrationData(task.id)) return idleCard(task, hooks.openSettings);

  switch (task.id) {
    case "integration_resend":
      return resendCard();
    case "integration_github":
      return githubCard();
    case "integration_stripe":
      return stripeCard();
    case "integration_spotify":
      return spotifyCard();
    case "integration_games":
      return gamesCard(task, hooks.wide);
    case "integration_system":
      return systemCard(task);
    case "integration_weather":
      return weatherCard(task);
    case "integration_notion":
      return notionCard();
    case "integration_calcom":
      return calcomCard();
    default:
      return idleCard(task, hooks.openSettings);
  }
}

export { clear };
