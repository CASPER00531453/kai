// Chat view — DOM port of PromptView / ChatBubble / TypingDotsView from
// IslandViewContent.swift.

import { h, svg, clear } from "./dom";
import { ICONS } from "./icons";
import { renderMarkdown } from "./markdown";
import { Bridge, type ChatContext } from "../core/bridge";
import { tx } from "../core/prefs";
import { Sound } from "../core/sound";
import { State, type ChatMessage } from "../core/state";
import type { ViewHost } from "./views";

let nextId = 1;

function bubble(message: ChatMessage): HTMLElement {
  if (message.role === "user") {
    return h(
      "div",
      { class: "chat-row user" },
      h("div", { class: "bubble", text: message.content }),
    );
  }
  const reply = h("div", { class: "reply" });
  renderMarkdown(reply, message.content);
  return h("div", { class: "chat-row" }, reply);
}

function typingDots(): HTMLElement {
  return h(
    "div",
    { class: "chat-row" },
    h("div", { class: "typing" }, h("i"), h("i"), h("i")),
  );
}

/** The coloured chip showing what the question is about (a dropped file). */
function contextChip(label: string): HTMLElement {
  const chip = h("div", { class: "chip" }, h("i", { class: "chip-dot" }), h("span", { text: label }));
  requestAnimationFrame(() => chip.classList.add("settled"));
  return chip;
}

export function buildPrompt(onHeightChange: () => void): ViewHost {
  const chipRow = h("div", { class: "chip-row" });
  const log = h("div", { class: "chat-log" });
  const input = h("input", {
    type: "text",
    class: "chat-input",
    placeholder: tx("ask"),
    spellcheck: "false",
  }) as HTMLInputElement;
  const send = h("button", { class: "send-btn", title: tx("send") }, svg(ICONS.arrowUp, 11));
  const snip = h("button", { class: "snip-btn", title: tx("snip"), onclick: () => Bridge.snip() }, svg(ICONS.crop, 14, { stroke: 2 }));
  const bar = h("div", { class: "chat-bar" }, snip, input, send);

  const el = h(
    "div",
    { class: "view" },
    h("div", { class: "card wash chat-card" }, h("div", { class: "chat-body" }, chipRow, log, bar)),
  );
  (el.querySelector(".card") as HTMLElement).style.setProperty("--wash", "rgba(99,102,241,0.5)");

  let sending = false;
  let renderedSig = "";
  draft = () => sending || input.value.trim() !== "";

  async function submit() {
    const query = input.value.trim();
    if (!query || sending) return;
    cancelSpokenClose();
    input.value = "";
    sending = true;
    Sound.play("send");

    State.chatHistory.push({ id: nextId++, role: "user", content: query });
    State.stateOverride = "thinking";
    State.notify();
    onHeightChange();

    const file = State.droppedFile;
    const context: ChatContext | null =
      State.chatHistory.length === 1 && file ? { kind: "file", name: file.name, path: file.path } : null;

    try {
      const reply = await Bridge.chatSend(query, context);
      State.chatHistory.push({ id: nextId++, role: "assistant", content: reply.text });
      State.stateOverride = null;
      Sound.play("finish");
    } catch (err) {
      State.stateOverride = null;
      State.noteMessage = String(err).replace(/^Error:\s*/, "");
      State.view = "note";
      Sound.play("error");
    } finally {
      sending = false;
      State.notify();
      onHeightChange();
      input.focus();
    }
  }

  send.addEventListener("click", () => void submit());
  input.addEventListener("keydown", (e) => {
    if ((e as KeyboardEvent).key === "Enter") {
      e.preventDefault();
      void submit();
    }
    State.lastActivity = performance.now(); // typing is activity; the island must not close on it
    e.stopPropagation(); // Escape closes the island, not the chat
  });

  return {
    el,
    sync() {
      const file = State.droppedFile;
      const wantChip = file?.name ?? "";
      if (chipRow.dataset.label !== wantChip) {
        chipRow.dataset.label = wantChip;
        clear(chipRow);
        if (wantChip) chipRow.append(contextChip(wantChip));
      }

      const thinking = State.stateOverride === "thinking";
      const sig = State.chatHistory.map((m) => `${m.id}:${m.content}`).join("|") + (thinking ? "?" : "") + (hearing ? "!" + hearingText : "");
      if (sig !== renderedSig) {
        renderedSig = sig;
        clear(log);
        for (const m of State.chatHistory) log.append(bubble(m));
        if (thinking) log.append(typingDots());
        if (hearing) log.append(h("div", { class: "chat-row" }, h("div", { class: "reply", text: hearingText })));
        log.scrollTop = log.scrollHeight;
      }

      input.placeholder = State.chatHistory.length === 0 ? tx("ask") : tx("more");
      send.title = tx("send");
      input.disabled = sending;
    },
    focus() {
      input.focus();
      input.select();
    },
  };
}

/**
 * A file was dropped: open the chat with its summary. Later questions go through
 * the normal box; the host remembers the file, so they are answered about it.
 */
export async function summarizeFile(onHeightChange: () => void) {
  const file = State.droppedFile;
  if (!file) return;
  State.chatHistory = [{ id: nextId++, role: "user", content: file.name }];
  State.stateOverride = "thinking";
  State.notify();
  onHeightChange();
  let answer: string;
  try {
    answer = (await Bridge.chatSend("", { kind: "file", name: file.name, path: file.path })).text;
    Sound.play("finish");
  } catch (err) {
    answer = String(err).replace(/^Error:\s*/, "");
    Sound.play("error");
  }
  State.chatHistory.push({ id: nextId++, role: "assistant", content: answer });
  State.stateOverride = null;
  State.notify();
  onHeightChange();
}

/** How long a spoken answer stays up once it has finished typing out. */
const SPOKEN_LINGER = 5000;
let spokenClose: number | null = null;
/** True while something is written in the chat box. Set by the view. */
let draft: () => boolean = () => false;

function cancelSpokenClose() {
  if (spokenClose != null) window.clearTimeout(spokenClose);
  spokenClose = null;
}

let voiceTimer: number | null = null;
let hearing = false;
let hearingText = "";

/** AltGr answer on v2: open the chat and type it out with a click, no voice. */
export function voiceTurn(kind: string, you: string, text: string, open: () => void, close: () => void) {
  const brand = document.getElementById("kai-brand");
  cancelSpokenClose();
  if (kind === "listen") {
    hearing = true;
    hearingText = text || tx("listen");
    if (brand) brand.textContent = hearingText;
    open();
    State.notify();
    return;
  }
  hearing = false;
  if (kind === "think") {
    if (brand) brand.textContent = text || tx("think");
    State.notify();
    return;
  }
  if (brand) brand.textContent = "Kai V2";
  open();
  State.stateOverride = null;
  if (you) State.chatHistory.push({ id: nextId++, role: "user", content: you });
  const id = nextId++;
  State.chatHistory.push({ id, role: "assistant", content: "" });
  State.notify();
  if (voiceTimer != null) window.clearInterval(voiceTimer);
  let i = 0;
  voiceTimer = window.setInterval(() => {
    i += 1;
    const msg = State.chatHistory.find((m) => m.id === id);
    if (msg) msg.content = text.slice(0, i);
    if (i % 2 === 0) Sound.typeTick();
    State.notify();
    if (i >= text.length && voiceTimer != null) {
      window.clearInterval(voiceTimer);
      voiceTimer = null;
      // A spoken question is answered and done: the island tucks itself away, unless
      // a reply is being typed. Typed conversations are never closed this way.
      spokenClose = window.setTimeout(() => {
        spokenClose = null;
        if (State.view === "prompt" && !draft()) close();
      }, SPOKEN_LINGER);
    }
  }, 32);
}
