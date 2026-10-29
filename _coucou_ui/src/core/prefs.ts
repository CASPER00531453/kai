// Kai's own preferences (language, voice), kept by the Python host. The island
// only mirrors them; every change goes through the host so both processes agree.

import { Sound } from "./sound";
import { State } from "./state";
import { setBodyColor } from "../mochi/palette";

// Menus are written in Turkish and English; every other language reads English.
const TEXT = {
  tr: {
    ask: "Bir şey sor…", more: "Devam et…", send: "Gönder", listen: "dinliyor", think: "bakıyorum",
    sound: "Ses efektleri", autoClose: "Otomatik kapan", language: "Dil", voice: "Kai sesi",
    quality: "Kalite", mic: "Sürekli dinle", allSettings: "Tüm ayarlar…", speak: "Sesli konuş",
    needsPermission: "izin istiyor", allow: "İzin ver", deny: "Reddet",
    hooksOn: "Claude Code bağlı", hooksOff: "Claude kancası kurulu değil",
    keyMissing: "Anahtar girilmemiş", loading: "Bağlı · yükleniyor…", refresh: "Yenile", open: "Aç",
    stars: "Toplam yıldız", repos: "Depolar", overview: "Genel", deployments: "Yayınlar", payments: "Ödemeler",
    nowPlaying: "Şimdi çalıyor", paused: "Duraklatıldı", nothingPlaying: "Bir şey çalmıyor",
    favSave: "Favorim yap", favPlay: "Favorimi çal", favorite: "Favori",
    games: "Oyunlar", system: "Sistem", weather: "Hava", installed: "kurulu", noGames: "Steam oyunu bulunamadı",
    cpu: "İşlemci", ram: "Bellek", gpu: "Ekran kartı", feels: "Hissedilen", wind: "Rüzgâr", noCity: "Şehir girilmemiş",
    city: "Şehir", startup: "Windows açılınca başlat", allGames: "Tüm oyunlar",
    hover: "Üzerine gelince aç", copy: "Kopyala", copied: "Kopyalandı", agents: "Ajanlar", wardrobe: "Gardırop",
    mascot: "Maskot", color: "Renk", asking: "soruyor", done: "Tamam", inTerminal: "Terminalde cevapla", snip: "Ekrandan seç (Alt+Shift+S)",
    dropHere: "Dosyanı buraya bırak", analyzing: "Analiz ediliyor", ready: "Hazır",
    check: "Güncellemeleri denetle", update: "Güncelle", updating: "İndiriliyor…", upToDate: "Güncel",
    codeDone: "Bitti", codeIdle: "Claude Code bir dosyaya dokununca değişiklik burada görünür.",
    accessory: "Aksesuar", accNone: "Yok", accWitch: "Cadı şapkası", accPumpkin: "Balkabağı",
    accBat: "Yarasa kanatları", accHorns: "Şeytan boynuzu", accVampire: "Vampir",
    updOut: "Kai {v} çıktı", updHave: "Sende {v} var", updNow: "Şimdi güncelle", updNews: "Yenilikler", updLater: "Sonra",
    updDownloading: "GitHub'dan indiriliyor… %{p}", updInstalling: "Kuruluyor… Kai kapanıp kendi açılacak.",
    updFailed: "Güncelleme olmadı", updGet: "GitHub'dan indir", ok: "Tamam",
    planReady: "planı hazır", planAuto: "Otomatik mod", planManual: "Manuel", planChange: "Planı değiştir",
    replyReady: "Yanıt hazır", desktopName: "Claude Desktop",
    focusStart: "Odak modu: 25 dk odak, 5 dk mola", focusStop: "Odak modunu bitir",
    always: "Her zaman izin ver",
    queue: "Sıra",
  },
  en: {
    ask: "Ask me anything…", more: "Continue…", send: "Send", listen: "listening", think: "on it",
    sound: "Sound effects", autoClose: "Auto-close", language: "Language", voice: "Kai's voice",
    quality: "Quality", mic: "Always listen", allSettings: "All settings…", speak: "Speak aloud",
    needsPermission: "needs permission", allow: "Allow", deny: "Deny",
    hooksOn: "Claude Code connected", hooksOff: "Claude hook not installed",
    keyMissing: "No key yet", loading: "Connected · loading…", refresh: "Refresh", open: "Open",
    stars: "Total stars", repos: "Repositories", overview: "Overview", deployments: "Deployments", payments: "Payments",
    nowPlaying: "Now playing", paused: "Paused", nothingPlaying: "Nothing is playing",
    favSave: "Make favourite", favPlay: "Play favourite", favorite: "Favourite",
    games: "Games", system: "System", weather: "Weather", installed: "installed", noGames: "No Steam games found",
    cpu: "Processor", ram: "Memory", gpu: "Graphics card", feels: "Feels like", wind: "Wind", noCity: "No city set",
    city: "City", startup: "Start with Windows", allGames: "All games",
    hover: "Open on hover", copy: "Copy", copied: "Copied", agents: "Agents", wardrobe: "Wardrobe",
    mascot: "Mascot", color: "Colour", asking: "is asking", done: "Done", inTerminal: "Answer in terminal", snip: "Pick from screen (Alt+Shift+S)",
    dropHere: "Drop your file here", analyzing: "Analysing", ready: "Ready",
    check: "Check for updates", update: "Update", updating: "Downloading…", upToDate: "Up to date",
    codeDone: "Done", codeIdle: "When Claude Code touches a file, the change shows up here.",
    accessory: "Accessory", accNone: "None", accWitch: "Witch hat", accPumpkin: "Pumpkin",
    accBat: "Bat wings", accHorns: "Devil horns", accVampire: "Vampire",
    updOut: "Kai {v} is out", updHave: "You have {v}", updNow: "Update now", updNews: "What's new", updLater: "Later",
    updDownloading: "Downloading from GitHub… {p} %", updInstalling: "Installing… Kai closes and comes back by itself.",
    updFailed: "The update didn't go through", updGet: "Get it on GitHub", ok: "OK",
    planReady: "has a plan ready", planAuto: "Auto mode", planManual: "Manual", planChange: "Change plan",
    replyReady: "Reply ready", desktopName: "Claude Desktop",
    focusStart: "Focus mode: 25 min focus, 5 min break", focusStop: "Stop focus mode",
    always: "Always allow",
    queue: "Queue",
  },
};

export type TextKey = keyof typeof TEXT.tr;
type Choice = [label: string, value: string];

export interface Prefs {
  language: string;
  languages: [code: string, name: string][];
  voice: string;
  voices: Choice[];
  model: string;
  models: Choice[];
  mic: boolean;
  /** Off means Kai only writes. */
  speak: boolean;
  /** Sound effects and their volume (0–0.2). */
  sfx: boolean;
  sfx_volume: number;
  /** What Kai is wearing. */
  accessory: string;
  /** Where the weather pill looks. */
  city: string;
  /** Kai starts when Windows does. */
  startup: boolean;
  /** The island opens when the pointer reaches it. */
  hover: boolean;
  /** What the bot wears, from the wardrobe. */
  outfit: string;
  /** Which mascot the bot is. */
  mascot: string;
  /** The body's colour as #rrggbb. */
  color: string;
  /** Other coding agents Kai can show: connected ones, and the ones found on this computer. */
  agents: { id: string; name: string; installed: boolean; present: boolean; path: string }[];
  /** What the last connect or disconnect had to say. */
  agentNote: string;
  /** Claude Code hooks point at this Kai. */
  hooks: boolean;
  /** A key is saved for the chosen provider. */
  api: boolean;
  version: string;
  updateLatest: string;
  updateAvailable: boolean;
  updateError: string;
  /** The release's notes and its page on GitHub. */
  updateNotes: string;
  updateUrl: string;
  /** The date and time in the middle of the compact island. */
  clock: boolean;
  /** Another pill finishing or failing opens the island for a moment. */
  alertsAll: boolean;
  /** The mascot shows how the computer feels. */
  feelsPc: boolean;
}

interface HostApi {
  prefs?: () => Promise<string>;
  set_pref?: (key: string, value: string | boolean | number) => Promise<string>;
  settings_window?: () => Promise<void>;
  update?: (action: string) => Promise<string>;
  update_phase?: () => Promise<string>;
  agent_set?: (agent: string, on: boolean) => Promise<string>;
}

const host = () => (window as unknown as { pywebview?: { api?: HostApi } }).pywebview?.api;

let lang: keyof typeof TEXT = "tr";
let current: Prefs | null = null;

export const tx = (key: TextKey) => TEXT[lang][key];
export const turkish = () => lang === "tr";

const PILL_NAMES: Record<string, TextKey> = {
  integration_games: "games",
  integration_system: "system",
  integration_weather: "weather",
};

/** A pill's name in the chosen language. */
export const pillName = (id: string, fallback: string) => (PILL_NAMES[id] ? tx(PILL_NAMES[id]) : fallback);
export const prefs = () => current;

function take(raw: string | null | undefined) {
  if (!raw) return;
  try {
    current = JSON.parse(raw) as Prefs;
  } catch {
    return;
  }
  lang = current.language === "tr" ? "tr" : "en";
  State.settings.hooksInstalled = current.hooks;
  State.settings.soundEnabled = current.sfx;
  // The island opens on a click only.
  State.settings.openOnHover = false;
  State.settings.mochiOutfit = current.outfit ?? "none";
  setBodyColor(current.color);
  State.settings.soundVolume = current.sfx_volume;
  Sound.setEnabled(current.sfx);
  Sound.setVolume(current.sfx_volume);
  State.notify();
}

/** False until the host bridge is up. */
export async function loadPrefs(): Promise<boolean> {
  const api = host();
  if (!api?.prefs) return false;
  take(await api.prefs());
  return true;
}

export async function setPref(
  key: "language" | "voice" | "model" | "mic" | "speak" | "sfx" | "sfx_volume" | "accessory" | "city" | "startup" | "hover" | "outfit" | "mascot" | "color",
  value: string | boolean | number,
) {
  take(await host()?.set_pref?.(key, value));
}

/** 'check' asks for a newer Kai; 'install' downloads it and restarts Kai; 'page' opens its release. */
export async function runUpdate(action: 'check' | 'install' | 'page' | 'dismiss') {
  take(await host()?.update?.(action));
}

export interface UpdatePhase {
  phase: "idle" | "downloading" | "installing" | "error";
  fraction: number;
  error: string;
}

/** Where the download of a new Kai stands. */
export async function updatePhase(): Promise<UpdatePhase> {
  try {
    const raw = await host()?.update_phase?.();
    if (raw) return JSON.parse(raw) as UpdatePhase;
  } catch {
    /* the card shows the offer again */
  }
  return { phase: "idle", fraction: 0, error: "" };
}

/** Connect or disconnect another agent's hooks. The host backs the file up first. */
export async function setAgent(agent: string, on: boolean) {
  take(await host()?.agent_set?.(agent, on));
}

export function openHostSettings() {
  void host()?.settings_window?.();
}
