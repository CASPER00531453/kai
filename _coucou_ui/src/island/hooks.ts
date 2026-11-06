// Claude Code hook events → island state.
// Port of HookServer.processEvent / processPermissionRequest from the macOS app.
// Difference from macOS: no terminal filter. On Windows the hook fires from any
// terminal (Windows Terminal, VS Code, PowerShell…) and all of them are handled.

import { Bridge, onEvent } from "../core/bridge";
import { codePrompt, codeStop, codeToolEnd, codeToolStart } from "../core/codefeed";
import { prefs, turkish } from "../core/prefs";
import { Sound } from "../core/sound";
import { State, type ApprovalInfo, type AskedQuestion } from "../core/state";
import type { Island } from "./island";
import { Focus } from "./focus";
import { Queue } from "../views/queue";

const CLAUDE_ID = "integration_claude";

interface HookPayload {
  hook_event_name?: string;
  request_id?: string;
  session_id?: string;
  cwd?: string;
  message?: string;
  /** Stop: the turn's answer, straight from Claude Code. */
  last_assistant_message?: string;
  /** The task Kai handed Claude from its queue at the end of this turn. */
  queued_next?: string;
  /** UserPromptSubmit carries `prompt`; `message` belongs to Notification/Stop. */
  prompt?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  /** PostToolUse of an edit: the changed lines, trimmed by the relay. */
  patch?: unknown;
  /** Optional agent tag: lowercase, digits and hyphens, ≤ 24 chars. */
  coucou_agent?: string;
  /** The session's /rename title and the folder it started in, read by the relay. */
  session_title?: string;
  session_root?: string;
  /** Stop / StopFailure: the session's terminal or editor is the window in front. */
  host_in_front?: boolean;
  /** The process of the session's terminal or editor, to bring it forward. */
  host_pid?: number;
  /** A question sent before Claude asks it (kai_hook.py --ask). */
  kai_ask?: boolean;
  /** Claude Code suggested rules to remember with this request. */
  can_always?: boolean;
}

/** Same rule as HookServer.validateAgent on macOS. "claude" is reserved. */
function validateAgent(raw: string | undefined): string | null {
  if (!raw || raw.length > 24 || raw === "claude") return null;
  if (!/^[a-z0-9-]+$/.test(raw)) return null;
  return raw;
}

/** How each agent's pill is called; an agent Kai does not know keeps its tag. */
const AGENT_NAMES: Record<string, string> = {
  codex: "Codex", copilot: "Copilot", gemini: "Gemini", antigravity: "Antigravity", cursor: "Cursor",
  muse: "Muse", opencode: "OpenCode", amp: "Amp", hermes: "Hermes",
  "claude-desktop": "Claude Desktop",
};

const FALLBACK_COLORS = ["#22C55E", "#EAB308", "#60A5FA", "#E879F9"];

function agentColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (Math.imul(31, h) + name.charCodeAt(i)) | 0;
  }
  return FALLBACK_COLORS[Math.abs(h) % FALLBACK_COLORS.length];
}

function lastPathComponent(p: string): string {
  const cleaned = p.replace(/[\\/]+$/, "");
  const idx = Math.max(cleaned.lastIndexOf("\\"), cleaned.lastIndexOf("/"));
  return idx >= 0 ? cleaned.slice(idx + 1) : cleaned;
}

/** What each tool is doing, as [Türkçe, English]. */
const TOOL_LABELS: Record<string, [string, string]> = {
  Bash: ["Çalıştırıyor", "Running"],
  Read: ["Okuyor", "Reading"],
  Write: ["Yazıyor", "Writing"],
  Edit: ["Düzenliyor", "Editing"],
  Glob: ["Arıyor", "Finding"],
  Grep: ["Arıyor", "Searching"],
  WebSearch: ["Web'de arıyor", "Web search"],
  WebFetch: ["İndiriyor", "Fetching"],
  TodoWrite: ["Görevler", "Tasks"],
  Task: ["Ajan", "Agent"],
  LS: ["Listeliyor", "Listing"],
  MultiEdit: ["Düzenliyor", "Editing"],
  NotebookEdit: ["Notebook", "Notebook"],
  PowerShell: ["Çalıştırıyor", "Running"],
  ask_question: ["Cevap bekliyor", "Needs input"],
};

/** Antigravity asking you something: its ask_question tool, maybe behind a server prefix. */
const isQuestionTool = (tool: string) => tool === "ask_question" || tool.endsWith(":ask_question");

function stepLabel(tool: string, input: Record<string, unknown>): string {
  const labelTool = isQuestionTool(tool) ? "ask_question" : tool;
  const label = TOOL_LABELS[labelTool]?.[turkish() ? 0 : 1] ?? tool;
  const str = (k: string) => (typeof input[k] === "string" ? (input[k] as string) : null);
  const cmd = str("command");
  if (cmd) return `${label} · ${cmd.slice(0, 40)}`;
  const path = str("path");
  if (path) return `${label} · ${lastPathComponent(path)}`;
  const file = str("file_path");
  if (file) return `${label} · ${lastPathComponent(file)}`;
  const query = str("query");
  if (query) return `${label} · ${query.slice(0, 40)}`;
  if (isQuestionTool(tool) && Array.isArray(input.questions)) {
    const first = input.questions[0] as Record<string, unknown> | undefined;
    const q = typeof first?.question === "string" ? first.question.trim() : "";
    if (q) return `${label} · ${q.slice(0, 40)}`;
  }
  return label;
}

/** A plan is too long for the card: its first non-empty line, without the Markdown heading marks. */
function planTitle(plan: unknown): string {
  const first = typeof plan === "string" ? plan.split("\n").find((l) => l.trim()) : undefined;
  const title = first ? first.replace(/^[#\s]+/, "").trim() : "";
  return title || "Plan";
}

/**
 * What the Allow button actually authorises. Approving "Write" tells you nothing
 * — approving `Write · C:\…\.env` tells you everything, and the difference is
 * the whole point of approving from the island rather than blind.
 *
 * Ordered by how specific the field is, so an unfamiliar tool still shows
 * whatever identifying string it carries instead of falling back to its name.
 */
const APPROVAL_FIELDS = [
  "command", // Bash, PowerShell
  "file_path", // Write, Edit, MultiEdit, NotebookEdit
  "path", // Read, LS
  "url", // WebFetch
  "query", // WebSearch
  "pattern", // Glob, Grep
  "prompt", // Task
] as const;

function approvalTarget(tool: string, input: Record<string, unknown>): string {
  for (const field of APPROVAL_FIELDS) {
    const value = input[field];
    if (typeof value === "string" && value.trim()) {
      return `${tool} · ${value.trim()}`;
    }
  }
  return tool;
}

/**
 * The questions of an AskUserQuestion call, if the island can show all of them
 * as options to pick from. Anything it cannot is left to the terminal.
 */
function askedQuestions(tool: string, input: Record<string, unknown>): AskedQuestion[] | null {
  if (tool !== "AskUserQuestion" || !Array.isArray(input.questions)) return null;
  const out: AskedQuestion[] = [];
  for (const raw of input.questions as Record<string, unknown>[]) {
    const question = typeof raw?.question === "string" ? raw.question : "";
    const options = (Array.isArray(raw?.options) ? (raw.options as Record<string, unknown>[]) : [])
      .filter((o) => typeof o?.label === "string" && o.label)
      .map((o) => ({
        label: o.label as string,
        description: typeof o.description === "string" ? o.description : "",
      }));
    // A question cut short by the relay would be answered under the wrong text.
    if (!question || question.endsWith("…") || options.length < 2) return null;
    out.push({ question, options, multiSelect: raw.multiSelect === true });
  }
  return out.length > 0 ? out : null;
}

// ── The Claude Code pill's name ──────────────────────────────────────────────
// After coucou's PillSessionRegistry: the pill is named after the session's
// /rename title, else the folder it started in (not a subfolder it moved into).
// With several sessions it follows the one at work: the oldest one mid-turn,
// else the one that worked last. A scratch session's folder is a meaningless
// "scratch-2026-…" id, so that one stays "Kai".

interface Session { name: string; cwd: string; working: boolean; lastWorked: number; seen: number }
const sessions = new Map<string, Session>();

function sessionName(payload: HookPayload): string {
  const title = (payload.session_title ?? "").trim();
  if (title) return title.slice(0, 28);
  const folder = lastPathComponent(payload.session_root || payload.cwd || "");
  if (!folder || /^scratch/i.test(folder) || /^[0-9a-f-]{20,}$/i.test(folder)) return "Kai";
  return folder.slice(0, 28);
}

function track(payload: HookPayload, working: boolean | null) {
  const id = payload.session_id || "?";
  const now = performance.now();
  const s = sessions.get(id) ?? { name: "Kai", cwd: "", working: false, lastWorked: 0, seen: now };
  s.name = sessionName(payload);
  if (payload.cwd) s.cwd = payload.cwd;
  if (working !== null) {
    s.working = working;
    s.lastWorked = now;
  }
  s.seen = now;
  sessions.delete(id);
  sessions.set(id, s); // insertion order is age order for the oldest-first scan below
  // A session silent for six hours is gone.
  for (const [key, other] of sessions) if (now - other.seen > 6 * 3600_000) sessions.delete(key);
}

/** The session whose name the pill shows. */
function displayOwner(): Session | null {
  let last: Session | null = null;
  const ordered = [...sessions.values()].sort((a, b) => a.seen - b.seen);
  for (const s of ordered) {
    if (s.working) return s;
    if (!last || s.lastWorked > last.lastWorked) last = s;
  }
  return last;
}

function upsert(cwd: string) {
  const t = State.tasks.find((x) => x.id === CLAUDE_ID);
  if (!t) return;
  const owner = displayOwner();
  t.name = owner?.name ?? "Kai";
  t.sessionCwd = owner?.cwd || cwd || t.sessionCwd;
}

function clearSession(sessionId: string | undefined) {
  sessions.delete(sessionId || "?");
  const t = State.tasks.find((x) => x.id === CLAUDE_ID);
  if (!t) return;
  if (sessions.size > 0) {
    upsert("");
    return;
  }
  t.steps = [];
  t.stepIndex = 0;
  delete t.stepSeq;
  t.name = "Kai";
  t.pillBadge = null;
}

// ── Alerts from every pill ───────────────────────────────────────────────────
// After coucou #683: with the setting on, another pill that finishes or fails
// takes the focus for its card; the pill that was shown comes back when the
// island closes. Never over an approval, a question, or a card in use.

let focusBeforeAlert: string | null = null;
let alertPill: string | null = null;
const ALERT_OVER = new Set(["overview", "finished", "error", "empty"]);

function showsAlert(pill: string, focused: boolean): boolean {
  if (focused) return true;
  if (!prefs()?.alertsAll || State.pendingApproval) return false;
  if (State.mode === "expanded" && !ALERT_OVER.has(State.view)) return false;
  if (focusBeforeAlert == null) focusBeforeAlert = State.focusId;
  alertPill = pill;
  State.focusId = pill;
  return true;
}

/** The island closed: the pill shown before another pill's alert comes back. */
export function restoreAlertFocus() {
  const prev = focusBeforeAlert;
  const borrowed = alertPill;
  focusBeforeAlert = null;
  alertPill = null;
  if (!prev || State.pendingApproval || State.focusId !== borrowed || borrowed === prev) return;
  if (State.tasks.some((t) => t.id === prev)) State.focusId = prev;
}

export function registerHookHandlers(island: Island) {
  void onEvent<HookPayload>("hook", (payload) => handleHook(island, payload));
}

/** Events relayed by the Python host, which has no event bus of its own. */
export function feedHooks(island: Island, payloads: unknown[]) {
  for (const payload of payloads) {
    if (payload && typeof payload === "object") handleHook(island, payload as HookPayload);
  }
}

/** Most requests waiting at once, the one on the card included (agents.MAX_PENDING). */
const MAX_PENDING = 5;

/**
 * The card is free: the oldest request still in line takes it, the way a new
 * one comes up. False when nobody is waiting.
 */
export function nextApproval(island: Island): boolean {
  const next = State.approvalQueue.shift();
  if (!next) return false;
  State.pendingApproval = next;
  State.isPinned = true;
  const view = next.questions ? "question" : "approval";
  State.updateTask(CLAUDE_ID, view);
  State.setPillBadge(CLAUDE_ID, State.approvalQueue.length ? "approval" : null);
  Sound.play("approval");
  island.alert(view);
  void Bridge.log(`sıradaki kart açıldı: ${next.tool} (${State.approvalQueue.length} bekliyor)`);
  State.notify();
  return true;
}

/**
 * Each request gives up on its own clock, on the card or still in line: a
 * little before the host stops waiting for it. By id, so it never takes down a
 * request that came later.
 */
function armRequestTimeout(island: Island, requestId: string, ms: number) {
  window.setTimeout(() => {
    if (State.approvalQueue.some((x) => x.requestId === requestId)) {
      State.approvalQueue = State.approvalQueue.filter((x) => x.requestId !== requestId);
      State.notify();
      return;
    }
    if (State.pendingApproval?.requestId !== requestId) return;
    State.pendingApproval = null;
    if (nextApproval(island)) return;
    State.isPinned = false;
    island.dropPin();
    State.updateTask(CLAUDE_ID, "working");
    State.setPillBadge(CLAUDE_ID, null);
    if (State.view === "approval" || State.view === "question") island.setView(State.defaultView());
    State.notify();
  }, ms);
}

/** The request was answered somewhere else (by voice, or in the terminal): take the card down. */
function settleApproval(island: Island, sessionId: string | undefined) {
  // Another session finishing a tool says nothing about this request.
  if (!State.pendingApproval || State.pendingApproval.sessionId !== (sessionId ?? "")) return;
  State.pendingApproval = null;
  if (nextApproval(island)) return;
  State.isPinned = false;
  island.dropPin();
  State.setPillBadge(CLAUDE_ID, null);
  if (State.view === "approval" || State.view === "question") island.setView(State.defaultView());
}

function handleHook(island: Island, payload: HookPayload) {
  // The phone started or stopped looking at the screen or the camera (phone_view.py).
  if (payload.hook_event_name === "KaiPhoneView") {
    const source = (payload as { source?: string }).source;
    State.phoneView = source === "camera" || source === "screen" ? source : null;
    void Bridge.log(`telefon görüntüsü: ${State.phoneView ?? "bitti"}`);
    if (State.phoneView) island.reveal();
    State.notify();
    return;
  }
  // Answered on the phone (phone_link.py): the card, or its place in line, goes.
  if (payload.hook_event_name === "KaiResolved") {
    const id = payload.request_id ?? "";
    State.approvalQueue = State.approvalQueue.filter((x) => x.requestId !== id);
    if (State.pendingApproval?.requestId === id) {
      State.pendingApproval = null;
      if (!nextApproval(island)) {
        State.isPinned = false;
        island.dropPin();
        State.updateTask(CLAUDE_ID, "working");
        State.setPillBadge(CLAUDE_ID, State.approvalQueue.length ? "approval" : null);
        if (State.view === "approval" || State.view === "question") island.setView(State.defaultView());
      }
      void Bridge.log("kart telefondan cevaplandı");
    }
    State.notify();
    return;
  }
  if (State.paused) {
    // Silence here used to cost Claude Code nearly two minutes: the relay waited
    // for a decision from an island that had already decided not to look. Say so,
    // and the terminal takes the question immediately.
    if (payload.request_id) {
      void Bridge.log(`kart açılmadı: ada duraklatılmış (${payload.tool_name})`);
      // Inside Kai the decline is an "ask": Claude takes the question at once.
      Bridge.approvalAsk(payload.request_id);
    }
    return;
  }

  const name = payload.hook_event_name ?? "";
  const cwd = payload.cwd ?? "";

  // Route to the right pill. Valid coucou_agent → dynamic "agent_<name>" pill.
  // "claude" is reserved; absent or invalid → Claude Code pill unchanged.
  const validAgent = validateAgent(payload.coucou_agent);
  const agentId = validAgent ? `agent_${validAgent}` : CLAUDE_ID;
  const isExternalAgent = validAgent !== null;

  const focused = State.focusId === agentId;
  // You are looking at the session's terminal: a finish or an error is already in
  // front of you, so the pill only takes a badge (no sound, no opening).
  // Focus mode keeps the news just as quiet.
  const inFront = payload.host_in_front === true || Focus.focusing;

  // Claude Code sessions behind the one pill: who is at work, and what it is called.
  if (!isExternalAgent && name) {
    const working = ["UserPromptSubmit", "PreToolUse", "PostToolUse"].includes(name)
      ? true
      : ["Stop", "StopFailure"].includes(name) ? false : null;
    if (name !== "SessionEnd") track(payload, working);
  }

  /** Alerts force the island open; work events only reveal the compact island. */
  const surface = (view: Parameters<Island["alert"]>[0], isAlert: boolean) => {
    if (State.mode === "expanded") {
      if (isAlert) island.setView(view);
    } else if (isAlert) {
      island.alert(view);
    } else if (State.mode === "hidden") {
      island.reveal();
    }
  };

  /** Ensure the agent pill exists (no-op for Claude Code). */
  const ensurePill = () => {
    if (isExternalAgent) {
      State.upsertExternalAgent(agentId, AGENT_NAMES[validAgent!] ?? validAgent!, agentColor(validAgent!));
    } else {
      upsert(cwd);
    }
  };

  switch (name) {
    case "SessionStart":
      ensurePill();
      surface("overview", false);
      Sound.play("work");
      break;

    case "UserPromptSubmit": {
      ensurePill();
      State.updateTask(agentId, "thinking");
      // The field is `prompt`; reading `message` meant this step was always blank.
      if (!isExternalAgent) codePrompt();
      const asked = payload.prompt ?? payload.message;
      if (asked) State.appendStep(agentId, asked.slice(0, 60));
      surface("overview", false);
      break;
    }

    case "PreToolUse": {
      ensurePill();
      const tool = payload.tool_name ?? "Tool";
      if (!isExternalAgent) codeToolStart(tool, payload.tool_input ?? {});
      if (isQuestionTool(tool)) {
        // Antigravity asks you something: the pill turns to a question, with a sound.
        State.updateTask(agentId, "question");
        State.appendStep(agentId, stepLabel(tool, payload.tool_input ?? {}));
        Sound.play("question");
        surface("overview", true);
      } else {
        State.updateTask(agentId, "working");
        State.appendStep(agentId, stepLabel(tool, payload.tool_input ?? {}));
        surface("overview", false);
      }
      break;
    }

    case "PostToolUse":
      settleApproval(island, payload.session_id);
      if (!isExternalAgent) codeToolEnd(payload.tool_name ?? "", payload.patch, false);
      State.updateTask(agentId, "working");
      break;

    case "PostToolUseFailure":
      if (!isExternalAgent) codeToolEnd(payload.tool_name ?? "", null, true);
      State.updateTask(agentId, "working");
      State.appendStep(agentId, "⚠ failed");
      break;

    case "Notification": {
      const message = payload.message ?? "";
      const lower = message.toLowerCase();
      if (lower.includes("rate limit") || lower.includes("limite d")) {
        State.updateTask(agentId, "ratelimit");
        Sound.play("rate");
      } else if (message.endsWith("?")) {
        State.updateTask(agentId, "question");
        State.appendStep(agentId, message);
      }
      break;
    }

    case "Stop":
      // Claude Desktop has no session to start: its pill comes with the reply.
      if (validAgent === "claude-desktop") ensurePill();
      settleApproval(island, payload.session_id);
      // A task from the queue was handed over: Claude goes straight on with it,
      // so there is nothing finished to show.
      if (payload.queued_next) {
        void Queue.run("list");
        State.appendStep(agentId, `${turkish() ? "Sıradaki işe geçti" : "On to the next task"}: ${String(payload.queued_next).slice(0, 120)}`);
        break;
      }
      if (!isExternalAgent) codeStop();
      State.updateTask(agentId, "finished");
      // Claude Code puts the turn's answer in the Stop payload itself.
      const finalText = (payload.last_assistant_message ?? payload.message ?? "").replace(/\s+/g, " ").trim();
      if (finalText) State.appendStep(agentId, finalText.slice(0, 160));
      // Kept apart from the steps: a subagent ending after the turn added a step
      // after this one, and the finished card showed "Subagent done" instead.
      const finished = State.tasks.find((x) => x.id === agentId);
      if (finished) finished.finalLine = finalText.slice(0, 220) || null;
      if (!inFront) Sound.play("finish");
      // A reply ready in the Claude app: the mascot jumps for it.
      if (validAgent === "claude-desktop") island.emote("happy");
      if (!inFront && State.view !== "code" && showsAlert(agentId, focused)) surface("finished", true);
      else State.setPillBadge(agentId, "finished");
      window.setTimeout(() => {
        if (isExternalAgent) {
          State.removeTask(agentId);
        } else {
          State.updateTask(agentId, "idle");
          State.setPillBadge(agentId, null);
        }
      }, 5200);
      break;

    case "StopFailure":
      State.updateTask(agentId, "error");
      if (!inFront) Sound.play("error");
      if (!inFront && showsAlert(agentId, focused)) surface("error", true);
      else State.setPillBadge(agentId, "error");
      break;

    case "SessionEnd":
      if (isExternalAgent) {
        State.removeTask(agentId);
      } else {
        State.updateTask(agentId, "idle");
        clearSession(payload.session_id);
      }
      break;

    case "SubagentStart":
      State.appendStep(agentId, turkish() ? "Yardımcı ajan başladı" : "Subagent started");
      break;

    case "SubagentStop":
      State.appendStep(agentId, turkish() ? "Yardımcı ajan bitti" : "Subagent done");
      break;

    case "PermissionRequest": {
      // External agents do not get an approval card — showing one would look like
      // a Claude Code request. Decline immediately so the agent re-asks in its
      // terminal. Approval support for other agents will come with Codex support.
      if (isExternalAgent) {
        if (payload.request_id) void Bridge.approvalDecline(payload.request_id);
        break;
      }

      const requestId = payload.request_id ?? "";
      void Bridge.log(`kart istendi: ${payload.tool_name} req=${requestId} mod=${State.mode} odak=${State.focusId} bekleyen=${State.pendingApproval?.requestId ?? "-"} durdu=${State.paused}`);
      // The same request again (already on the card or in line): leave it be.
      if (State.pendingApproval?.requestId === requestId || State.approvalQueue.some((x) => x.requestId === requestId)) break;
      // Several sessions can ask at once: they wait their turn on the card. Past
      // the cap the newest goes back to its terminal.
      if ((State.pendingApproval ? 1 : 0) + State.approvalQueue.length >= MAX_PENDING) {
        void Bridge.log(`kart açılmadı: ${MAX_PENDING} istek zaten sırada`);
        if (requestId) Bridge.approvalAsk(requestId);
        break;
      }
      upsert(cwd);
      const tool = payload.tool_name ?? "Tool";
      const input = payload.tool_input ?? {};
      // Claude Code asking a question is not a permission to grant: it gets the
      // question card, with the options to pick from.
      const questions = askedQuestions(tool, input);
      const info: ApprovalInfo = {
        requestId,
        sessionId: payload.session_id ?? "",
        tool,
        // A plan is approved by its title: the whole of it is too long for the card.
        command: tool === "ExitPlanMode" ? planTitle(input.plan) : approvalTarget(tool, input),
        ...(questions ? { questions } : {}),
        ...(payload.host_pid ? { hostPid: payload.host_pid } : {}),
        ...(payload.can_always ? { canAlways: true } : {}),
      };
      // Coucou answers within 108 s or not at all; after that the terminal has
      // taken over and the card would be lying. A little before the host gives
      // up (45 s for a question sent ahead, else 108 s).
      armRequestTimeout(island, requestId, payload.kai_ask ? 43_000 : 105_000);
      if (State.pendingApproval) {
        // Another card is up: this one waits in line, the pill badged, and the
        // card on screen stays as it is.
        State.approvalQueue.push(info);
        State.setPillBadge(CLAUDE_ID, "approval");
        Sound.play("approval");
        if (requestId) void Bridge.approvalAck(requestId);
        void Bridge.log(`kart sıraya girdi: ${tool} (${State.approvalQueue.length} bekliyor)`);
        break;
      }
      State.pendingApproval = info;
      // The relay's short ack window closes in 800 ms; everything below this
      // line is synchronous, so the card really is up by the time it lands.
      if (requestId) void Bridge.approvalAck(requestId);
      State.updateTask(CLAUDE_ID, questions ? "question" : "approval");
      State.isPinned = true;
      Sound.play("approval");
      // A request or a question waits on a human: it always gets its card, even
      // when another pill is shown. A badge alone went unnoticed, and Claude sat
      // waiting the whole two minutes. The pill that was shown comes back once
      // the island closes (restoreAlertFocus).
      if (!focused) {
        if (focusBeforeAlert == null) focusBeforeAlert = State.focusId;
        alertPill = CLAUDE_ID;
        State.focusId = CLAUDE_ID;
      }
      island.alert(questions ? "question" : "approval");
      void Bridge.log(`kart açıldı: ${questions ? `soru (${questions.length})` : "izin"} mod=${State.mode} görünüm=${State.view}`);
      break;
    }

    default:
      break;
  }
  State.notify();
}
