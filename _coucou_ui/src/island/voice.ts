// What the island shows while Kai hears someone: the mascot hops with the voice
// (AltGr, OK Kai, dictation), short notes in the pill, and the notetaker's red
// dot with its clock.

import type { Island } from "./island";

type Api = { level?: () => Promise<number>; record?: () => Promise<void> };
const api = () => (window as unknown as { pywebview?: { api?: Api } }).pywebview?.api;

let island: Island | null = null;
let levelTimer: number | null = null;
let noteTimer: number | null = null;
let recordTimer: number | null = null;
let recordStart = 0;
let dictating = false;

const brand = () => document.getElementById("kai-brand");

export function attachVoice(target: Island) {
  island = target;
}

/** Asks the host for the microphone's level about fifteen times a second, only while someone talks to Kai. */
export function followVoice(on: boolean) {
  if (on && levelTimer == null) {
    levelTimer = window.setInterval(async () => {
      const level = (await api()?.level?.()) ?? 0;
      island?.setVoice(level);
    }, 66);
  } else if (!on && levelTimer != null) {
    window.clearInterval(levelTimer);
    levelTimer = null;
    island?.setVoice(0);
  }
}

function showBrand() {
  const el = brand();
  if (!el) return null;
  return el;
}

function resetBrand() {
  const el = brand();
  if (!el) return;
  if (recordTimer != null) return; // the recording's clock owns the pill
  el.classList.remove("dictating", "recording", "note");
  el.textContent = "Kai V2";
}

/** A short line in the pill for a few seconds. */
export function pillNote(text: string, ms = 3200) {
  const el = showBrand();
  if (!el || !text) return;
  if (noteTimer != null) window.clearTimeout(noteTimer);
  el.classList.add("note");
  el.textContent = text;
  noteTimer = window.setTimeout(() => {
    noteTimer = null;
    el.classList.remove("note");
    if (recordTimer != null) tickRecord();
    else resetBrand();
  }, ms);
}

/** Dictation notes from the host: start, typing, end (with an optional message). */
export function dictationNote(kind: string, text: string) {
  const el = showBrand();
  if (kind === "dictate") {
    dictating = true;
    followVoice(true);
    if (el) {
      el.classList.add("dictating");
      el.textContent = text;
    }
    return;
  }
  if (kind === "dictate-busy") {
    followVoice(false);
    if (el) el.textContent = text;
    return;
  }
  dictating = false;
  followVoice(false);
  if (el) el.classList.remove("dictating");
  if (text) pillNote(text);
  else resetBrand();
}

function tickRecord() {
  const el = brand();
  if (!el || noteTimer != null) return;
  const s = Math.max(0, Math.round((Date.now() - recordStart) / 1000));
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  el.classList.add("recording");
  el.textContent = `● ${mm}:${ss}`;
}

export function recordingNote(on: boolean) {
  if (on) {
    recordStart = Date.now();
    if (recordTimer == null) recordTimer = window.setInterval(tickRecord, 1000);
    tickRecord();
    return;
  }
  if (recordTimer != null) window.clearInterval(recordTimer);
  recordTimer = null;
  const el = brand();
  el?.classList.remove("recording");
  pillNote(document.documentElement.lang === "en" ? "Writing the notes…" : "Notları yazıyorum…", 4000);
}

export const isDictating = () => dictating;
