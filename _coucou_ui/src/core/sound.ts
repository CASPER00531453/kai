// SoundEngine — port of SoundEngine.swift.
// The 28 WAVs are the macOS app's own files (see SOUNDS_DIR in vite.config.ts);
// they are served at /sounds/<name>.wav. Default volume 0.12, slider range 0–0.2,
// exactly like the Mac player, and several sounds may overlap.

export const SOUND_NAMES = [
  "peek", "open", "close", "hover", "blip", "slap", "annoyed", "dizzy", "greet",
  "work", "finish", "error", "approval", "question", "approve", "gulp", "tick",
  "send", "love", "pop", "proud", "wink", "yawn", "attach", "think", "search",
  "rate", "sleep",
] as const;

export type SoundName = (typeof SOUND_NAMES)[number];

/** One note: start (s), from Hz, to Hz, length (s), level, wave. */
type Note = [at: number, from: number, to: number, length: number, level: number, type?: OscillatorType];

// Kai's own effects, made from plain oscillators so nothing has to ship as a file.
const RECIPES: Record<string, Note[]> = {
  blip: [[0, 740, 740, 0.07, 0.5]],
  hover: [[0, 980, 1100, 0.04, 0.25]],
  tick: [[0, 1250, 1250, 0.03, 0.3, "triangle"]],
  peek: [[0, 520, 780, 0.11, 0.45]],
  open: [[0, 440, 440, 0.08, 0.5], [0.07, 660, 660, 0.12, 0.5]],
  close: [[0, 560, 560, 0.07, 0.45], [0.06, 370, 370, 0.12, 0.45]],
  send: [[0, 420, 940, 0.14, 0.5, "triangle"]],
  pop: [[0, 300, 900, 0.06, 0.5]],
  attach: [[0, 620, 620, 0.05, 0.45], [0.06, 820, 820, 0.08, 0.45]],
  gulp: [[0, 620, 180, 0.18, 0.6]],
  greet: [[0, 523, 523, 0.11, 0.5], [0.11, 659, 659, 0.11, 0.5], [0.22, 784, 784, 0.11, 0.5], [0.33, 1047, 1047, 0.24, 0.5]],
  work: [[0, 392, 392, 0.09, 0.4], [0.09, 523, 523, 0.14, 0.4]],
  think: [[0, 494, 494, 0.09, 0.35], [0.12, 494, 554, 0.12, 0.35]],
  search: [[0, 600, 900, 0.1, 0.35], [0.12, 600, 900, 0.1, 0.35]],
  finish: [[0, 523, 523, 0.1, 0.55], [0.1, 659, 659, 0.1, 0.55], [0.2, 784, 784, 0.26, 0.55]],
  approve: [[0, 660, 660, 0.08, 0.55], [0.08, 990, 990, 0.2, 0.55]],
  proud: [[0, 659, 659, 0.09, 0.5], [0.09, 880, 880, 0.09, 0.5], [0.18, 1319, 1319, 0.24, 0.5]],
  love: [[0, 784, 784, 0.1, 0.45], [0.1, 988, 988, 0.1, 0.45], [0.2, 1175, 1175, 0.28, 0.45]],
  wink: [[0, 1047, 1319, 0.09, 0.4]],
  approval: [[0, 880, 880, 0.1, 0.6, "triangle"], [0.16, 880, 880, 0.1, 0.6, "triangle"], [0.32, 1175, 1175, 0.2, 0.6, "triangle"]],
  question: [[0, 587, 587, 0.1, 0.5], [0.11, 784, 880, 0.18, 0.5]],
  error: [[0, 233, 233, 0.14, 0.6, "sawtooth"], [0.14, 175, 175, 0.24, 0.6, "sawtooth"]],
  rate: [[0, 330, 330, 0.12, 0.5, "triangle"], [0.14, 262, 262, 0.2, 0.5, "triangle"]],
  slap: [[0, 190, 70, 0.09, 0.8, "square"]],
  annoyed: [[0, 300, 220, 0.16, 0.5, "sawtooth"]],
  dizzy: [[0, 500, 300, 0.14, 0.45], [0.14, 300, 520, 0.14, 0.45], [0.28, 520, 280, 0.2, 0.45]],
  yawn: [[0, 440, 220, 0.5, 0.35]],
  sleep: [[0, 330, 262, 0.35, 0.3]],
};

class SoundEngine {
  enabled = true;
  volume = 0.12;

  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private buffers = new Map<string, AudioBuffer>();
  private loading: Promise<void> | null = null;
  private idleTimer: number | null = null;

  /** Creates the context and decodes every WAV. Safe to call more than once. */
  preload(): Promise<void> {
    if (this.loading) return this.loading;
    this.loading = (async () => {
      const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return;
      const ctx = new Ctor();
      this.ctx = ctx;
      const master = ctx.createGain();
      master.gain.value = this.volume;
      master.connect(ctx.destination);
      this.master = master;
      await Promise.all(
        SOUND_NAMES.map(async (name) => {
          try {
            const res = await fetch(`/sounds/${name}.wav`);
            if (!res.ok) return;
            const buf = await ctx.decodeAudioData(await res.arrayBuffer());
            this.buffers.set(name, buf);
          } catch {
            /* a missing sound must never break the island */
          }
        }),
      );
    })();
    return this.loading;
  }

  /** WebView2 can hand us a suspended context; call after any user input. */
  resume() {
    if (this.idleTimer != null) {
      window.clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
    void this.ctx?.resume();
  }

  /**
   * Called when the island goes quiet. A running AudioContext keeps an audio
   * thread and its render quantum alive even with nothing playing, which shows
   * up as a steady trickle of CPU on a machine that is supposed to be idle.
   *
   * The delay covers the tail of whatever just played — suspending mid-sound
   * would clip it — and `play()` resumes the context on its own.
   */
  idle() {
    if (!this.ctx || this.ctx.state !== "running" || this.idleTimer != null) return;
    this.idleTimer = window.setTimeout(() => {
      this.idleTimer = null;
      void this.ctx?.suspend();
    }, 1500);
  }

  setVolume(v: number) {
    this.volume = Math.max(0, Math.min(0.2, v));
    if (this.master) this.master.gain.value = this.volume;
  }

  setEnabled(on: boolean) {
    this.enabled = on;
  }

  play(name: SoundName | string) {
    if (!this.enabled) return;
    const ctx = this.ctx;
    const master = this.master;
    const buf = this.buffers.get(name);
    if (!ctx || !master || !buf) {
      this.tone(name);
      return;
    }
    if (this.idleTimer != null) {
      window.clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }
    if (ctx.state === "suspended") void ctx.resume();
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(master);
    src.start();
  }

  /** Original clicks. Coucou's wav files stay where they are. */
  private tone(name: string) {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return;
    if (!this.ctx) {
      this.ctx = new Ctor();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.volume;
      this.master.connect(this.ctx.destination);
    }
    const ctx = this.ctx;
    const master = this.master;
    if (!master) return;
    if (ctx.state === "suspended") void ctx.resume();
    const now = ctx.currentTime;
    for (const [at, from, to, length, level, type] of RECIPES[name] ?? RECIPES.blip) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type ?? "sine";
      osc.frequency.setValueAtTime(from, now + at);
      if (to !== from) osc.frequency.exponentialRampToValueAtTime(to, now + at + length);
      // A few milliseconds of attack keep the note from clicking.
      gain.gain.setValueAtTime(0.0001, now + at);
      gain.gain.exponentialRampToValueAtTime(level, now + at + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + at + length);
      osc.connect(gain);
      gain.connect(master);
      osc.start(now + at);
      osc.stop(now + at + length + 0.02);
    }
  }

  /** Short click while a written answer types out. Does not need a wav file. */
  typeTick() {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctor || !this.enabled) return;
    if (!this.ctx) {
      this.ctx = new Ctor();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.volume;
      this.master.connect(this.ctx.destination);
    }
    const ctx = this.ctx;
    const master = this.master;
    if (!master) return;
    if (ctx.state === "suspended") void ctx.resume();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "square";
    osc.frequency.value = 1400;
    gain.gain.value = 0.04;
    osc.connect(gain);
    gain.connect(master);
    const now = ctx.currentTime;
    gain.gain.setValueAtTime(0.04, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.03);
    osc.start(now);
    osc.stop(now + 0.032);
  }
}

export const Sound = new SoundEngine();
