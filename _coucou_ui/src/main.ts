/// <reference types="vite/client" />
// Entry point: boot the bridge, wire the island, start the greeting.

import "./style.css";
import { Bridge, IS_TAURI, onEvent } from "./core/bridge";
import { Sound } from "./core/sound";
import { State, type Settings } from "./core/state";
import { Island } from "./island/island";
import { feedHooks, registerHookHandlers } from "./island/hooks";
import { feedIntegrations, registerIntegrationHandlers, refreshConfigured, type HostCard } from "./island/integrations";
import { loadPrefs } from "./core/prefs";
import { offerUpdate } from "./island/update";
import type { Mood } from "./mochi/mood";
import { usagePct, type UsageSnapshot } from "./core/usage";
import { Summary, type DailyReport } from "./views/summary";
import { Queue } from "./views/queue";
import { voiceTurn } from "./views/chat";
import { attachVoice, dictationNote, followVoice, recordingNote } from "./island/voice";

async function main() {
  const root = document.getElementById("root");
  if (!root) return;

  void Sound.preload();

  const island = new Island(root);
  attachVoice(island);

  const boot = await Bridge.boot();
  if (boot) {
    State.settings = { ...State.settings, ...boot.settings };
  }
  island.applySettings();
  State.loadIntegrationTasks();

  await onEvent<{ x: number; y: number }>("cursor", ({ x, y }) => island.onCursor(x, y));

  /** Pause has to reach Rust too, or the pollers keep calling out. */
  const setPaused = (on: boolean) => {
    if (State.paused === on) return;
    State.paused = on;
    void Bridge.setPaused(on);
  };

  await onEvent<string>("tray", (what) => {
    switch (what) {
      case "settings":
        setPaused(false);
        island.alert("settings");
        break;
      case "open":
        setPaused(false);
        island.alert(State.defaultView());
        break;
      case "pause":
        setPaused(!State.paused);
        if (State.paused) island.fsm.forceHidden();
        else island.reveal();
        break;
    }
  });

  await onEvent<null>("screen-changed", () => void Bridge.reposition());

  // The settings window writes preferences; apply them here without a restart.
  await onEvent<Settings>("settings-changed", (s) => {
    State.settings = { ...State.settings, ...s };
    island.applySettings();
    State.loadIntegrationTasks();
    void refreshConfigured();
  });

  registerHookHandlers(island);
  registerIntegrationHandlers(island);

  island.launch();
  // `npm run dev` only: the island at hand in the console, to bring up any card.
  if (import.meta.env.DEV) (window as unknown as { __island?: unknown }).__island = island;

  let prefsLoaded = false;

  window.setInterval(async () => {
    const api = (window as unknown as {
      pywebview?: {
        api?: {
          poll?: () => Promise<string>;
          line?: () => Promise<string>;
          hooks?: () => Promise<string>;
          services?: () => Promise<string>;
          log?: (message: string) => void;
        };
      };
    }).pywebview?.api;
    if (!api?.line) return;
    if (!prefsLoaded) {
      prefsLoaded = await loadPrefs();
      if (prefsLoaded) {
        offerUpdate(island);
        void Queue.run("list");
      }
    }
    let cards: string | undefined;
    let hooks: string | undefined;
    let raw: string | undefined;
    let vitals: (Mood & { woke?: boolean; summary?: string }) | undefined;
    let usage: UsageSnapshot | undefined;
    let report: DailyReport | undefined;
    if (api.poll) {
      // One trip to the host for all three; it answers with nothing when nothing is new.
      const all = await api.poll();
      if (!all) return;
      let changed = false;
      try {
        ({ cards, hooks, line: raw, prefs: changed = false, vitals, usage, report } = JSON.parse(all) as {
          cards?: string; hooks?: string; line?: string; prefs?: boolean; vitals?: Mood & { woke?: boolean; summary?: string };
          usage?: UsageSnapshot; report?: DailyReport;
        });
      } catch {
        return;
      }
      if (changed) {
        await loadPrefs();
        island.applySettings();
      }
      if (vitals) island.setMood(vitals);
      // The evening summary, once a day at the time set in the settings.
      if (report?.lines?.length) {
        Summary.report = report;
        island.alert("summary");
        Sound.play("finish");
      }
      if (usage) {
        // Crossing 80 % and 95 % of a limit: the mascot is startled, once each.
        const before = usagePct(State.usage) ?? 0;
        State.usage = usage;
        const now = usagePct(usage) ?? 0;
        if ((before < 80 && now >= 80) || (before < 95 && now >= 95)) {
          island.emote("surprised");
          Sound.play("approval");
          island.reveal();
        }
        State.notify();
      }
      // A newer Kai that GitHub has: its card, once, when nothing else waits.
      offerUpdate(island);
    } else {
      cards = await api.services?.();
      hooks = await api.hooks?.();
      raw = await api.line();
    }
    if (cards) {
      try {
        feedIntegrations(island, JSON.parse(cards) as Record<string, HostCard>);
        // Music on the computer: the mascot dances to it.
        island.setDancing(Boolean(State.integrations.integration_spotify?.data?.playing));
      } catch (err) {
        // A bad card must not break the island, but it must not vanish either.
        api.log?.(`kart: ${String(err)}`);
      }
    }
    if (hooks) {
      try {
        feedHooks(island, JSON.parse(hooks) as unknown[]);
      } catch (err) {
        api.log?.(`kanca: ${String((err as Error)?.stack ?? err)}`);
      }
    }
    if (!raw) return;
    await loadPrefs();
    try {
      const msg = JSON.parse(raw) as { kind?: string; text?: string; you?: string };
      const kind = msg.kind || "";
      if (kind.startsWith("dictate")) {
        dictationNote(kind, msg.text || "");
        return;
      }
      if (kind === "record" || kind === "record-end") {
        recordingNote(kind === "record");
        return;
      }
      // Listening (AltGr or « OK Kai »): the mascot hops with the voice until Kai starts thinking.
      followVoice(kind === "listen");
      if (kind === "answer" && !msg.text && !msg.you) {
        island.collapse();
        return;
      }
      voiceTurn(kind, msg.you || "", msg.text || "", () => island.alert("prompt"), () => island.collapse());
    } catch {
      /* a bad note must not break the island */
    }
  }, 400);

  // In a plain browser there is no wake strip behind the cursor: make the whole
  // page wake the island so the visuals can be checked with `npm run dev`.
  if (!IS_TAURI) {
    document.addEventListener("click", () => Sound.resume(), { once: true });
  }
}

// Anything the page throws ends up in kai.log; a frozen island should leave a trace.
function report(what: string) {
  (window as unknown as { pywebview?: { api?: { log?: (m: string) => void } } }).pywebview?.api?.log?.(what);
}
window.addEventListener("error", (e) => report(`hata: ${e.message} @ ${e.filename.split("/").pop()}:${e.lineno}`));
window.addEventListener("unhandledrejection", (e) => report(`söz: ${String((e.reason as Error)?.stack ?? e.reason)}`));

void main();
