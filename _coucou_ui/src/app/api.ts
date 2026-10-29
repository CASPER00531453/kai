// The Kai window's line to its Python host (app_window.py). Every call returns
// JSON as text; these wrappers parse it and fall back to something harmless when
// the page is opened outside the app (vite dev).

export interface Choice { 0: string; 1: string }

export interface ModelInfo {
  id: string; title: string; about: string; size: number;
  ready: boolean; busy: boolean; done: number; error: string;
}

export interface Agent { id: string; name: string; installed: boolean; present: boolean; path: string }

export interface RecorderStatus {
  recording: boolean; processing: boolean; started: number; seconds: number;
  live: { who: "me" | "them"; t: number; text: string }[];
  error: string; last_id: string; mic: number; system: number;
}

export interface HostStatus {
  recorder?: RecorderStatus;
  dictation?: string;
  ok_kai?: boolean;
  ok_kai_error?: string;
}

export interface AppState {
  island: Record<string, unknown> & {
    language: string; languages: [string, string][]; voice: string; voices: [string, string][];
    model: string; models: [string, string][]; mic: boolean; speak: boolean; sfx: boolean; sfx_volume: number;
    accessory: string; city: string; startup: boolean; outfit: string; mascot: string; color: string;
    agents: Agent[]; agentNote: string; hooks: boolean; api: boolean; version: string;
    updateLatest: string; updateAvailable: boolean; updateError: string;
  };
  flow: {
    dictation: boolean; dictation_key: string; stt_engine: string;
    ok_kai: boolean; ok_kai_sense: string; app_on_launch: boolean;
    tour_done: boolean; mail_address: string; mail_server: string;
    show_clock: boolean; alerts_all_pills: boolean; feels_pc: boolean;
    claude_desktop_chat: boolean; update_checks: boolean;
    summary_enabled: boolean; summary_time: string;
  };
  brain: {
    provider: string; providers: [string, string][]; api_url: string; api_model: string;
    keys: Record<string, boolean>;
  };
  models: ModelInfo[];
  agents: Agent[];
  status: HostStatus;
  version: string;
  update: { available: boolean; latest: string; error: string; current: string };
  language: string;
}

export interface FlowData {
  dictionary: ({ word: string } | { from: string; to: string })[];
  snippets: { trigger: string; text: string }[];
  styles: { enabled: boolean; default: string; apps: Record<string, string> };
  settings: { keep_days: number };
  stats: {
    dictations: number; words: number; saved_seconds: number; wpm: number;
    days: { day: string; words: number }[];
    apps: { app: string; words: number }[];
    recent: { at: number; text: string; app: string; words: number; style: string }[];
  };
}

export interface Note {
  id: string; title: string; started: number; seconds: number;
  speakers: Record<string, string>;
  transcript: { speaker: number; start: number; end: number; text: string }[];
  summary: string; key_points: string[]; todos: string[]; engine: string;
}

type Host = Record<string, (...args: unknown[]) => Promise<string>>;

const host = (): Host | undefined => (window as unknown as { pywebview?: { api?: Host } }).pywebview?.api;

export const ready = () =>
  new Promise<void>((resolve) => {
    if (host()) return resolve();
    window.addEventListener("pywebviewready", () => resolve(), { once: true });
    // In a plain browser there is no host; the page still draws.
    window.setTimeout(resolve, 1500);
  });

async function call<T>(name: string, fallback: T, ...args: unknown[]): Promise<T> {
  const fn = host()?.[name];
  if (!fn) return fallback;
  try {
    const raw = await fn(...args);
    return raw == null || raw === "" ? fallback : (JSON.parse(raw) as T);
  } catch (err) {
    void host()?.log?.(`${name}: ${String(err)}`);
    return fallback;
  }
}

export const Api = {
  state: () => call<AppState | null>("state", null),
  status: () => call<{ status: HostStatus; models: ModelInfo[] } | null>("status", null),
  set: (key: string, value: unknown) => call<AppState | null>("set", null, key, value),
  secret: (key: string, value: string) => call<AppState | null>("secret", null, key, value),
  checkKey: () => call<string>("check_key", "unknown"),
  modelDownload: (id: string) => call<unknown>("model_download", null, id),
  modelRemove: (id: string) => call<unknown>("model_remove", null, id),
  flow: () => call<FlowData | null>("flow_get", null),
  flowSet: (what: string, data: unknown) => call<FlowData | null>("flow_set", null, what, data),
  pasteLast: () => call<unknown>("paste_last", null),
  tryStyle: (text: string, style: string) => call<string>("try_style", text, text, style),
  record: (on: boolean) => call<{ status: HostStatus } | null>("record", null, on),
  notes: () => call<{ id: string; title: string; started: number; seconds: number }[]>("notes", []),
  note: (id: string) => call<Note | null>("note", null, id),
  noteRename: (id: string, n: string, name: string) => call<Note | null>("note_rename", null, id, n, name),
  noteDelete: (id: string) => call<unknown>("note_delete", null, id),
  noteMarkdown: (id: string) => call<string>("note_markdown", "", id),
  noteExport: (id: string) => call<string>("note_export", "", id),
  agentSet: (id: string, on: boolean) => call<AppState | null>("agent_set", null, id, on),
  update: (action: string) => call<AppState | null>("update", null, action),
  feedbackInbox: (fetch: boolean) => call<{ enabled: boolean; error: string; items: { id: string; at: number; stars: number; text: string; meta: string; crash?: boolean }[] }>("feedback_inbox", { enabled: false, error: "", items: [] }, fetch),
  feedbackDelete: (id: string) => call<{ enabled: boolean; error: string; items: { id: string; at: number; stars: number; text: string; meta: string; crash?: boolean }[] }>("feedback_delete", { enabled: false, error: "", items: [] }, id),
  feedback: (stars: number, text: string) => call<{ ok: boolean; error: string }>("feedback", { ok: false, error: "bridge" }, stars, text),
  openUrl: (url: string) => call<unknown>("open_url", null, url),
  openLicense: () => call<unknown>("open_license", null),
  openFolder: (which: string) => call<unknown>("open_folder", null, which),
  mailTest: () => call<{ ok: boolean; text: string }>("mail_test", { ok: false, text: "" }),
  calendarTest: () => call<string>("calendar_test", ""),
  report: (note: string) => call<{ zip: string; text: string } | null>("report", null, note),
};
