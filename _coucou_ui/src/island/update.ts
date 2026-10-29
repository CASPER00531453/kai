// New versions in the island — after coucou's island/update.ts. The host looks
// at GitHub a few times a day (updater.py); when it found a newer Kai, the card
// opens once, and only when nothing else waits on the island. "Later" keeps it
// away for a day for that version.

import { prefs } from "../core/prefs";
import { Sound } from "../core/sound";
import { State } from "../core/state";

const KEY = "kai.update.later";
const DAY = 24 * 3600 * 1000;
let shown = "";

function laterFor(version: string): boolean {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "{}") as { v?: string; at?: number };
    return saved.v === version && Date.now() - (saved.at ?? 0) < DAY;
  } catch {
    return false;
  }
}

export function updateLater(version: string) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ v: version, at: Date.now() }));
  } catch {
    /* the card may come back next start */
  }
}

/** Called whenever the preferences are read again. */
export function offerUpdate(island: { alert(view: "update"): void; emote(name: "surprised"): void }) {
  const p = prefs();
  const latest = p?.updateLatest ?? "";
  if (!p?.updateAvailable || !latest || shown === latest || laterFor(latest)) return;
  // Never over a question, an approval, or a card the user is busy in.
  if (State.paused || State.pendingApproval || State.mode === "expanded") return;
  shown = latest;
  island.alert("update");
  island.emote("surprised");
  Sound.play("peek");
}
