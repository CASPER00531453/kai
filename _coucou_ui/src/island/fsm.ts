// Island open/close FSM — port of IslandStateMachine.swift.
// No DOM, no Tauri: it only reports transitions.

export type FsmState = "hidden" | "petit" | "home" | "coucou";

export class IslandStateMachine {
  state: FsmState = "hidden";

  onTransition: ((from: FsmState, to: FsmState) => void) | null = null;

  /** home → petit delay, seconds. */
  homeToPetitDelay = 10;
  /** petit → hidden delay, seconds. */
  petitToHiddenDelay = 60;
  /** coucou → petit once the greeting animation ends (no hover). */
  greetAutoCollapseDelay = 0.6;
  /** coucou → petit while the mouse hovers the greeting. */
  greetHoverCollapseDelay = 10;
  /** An alert waiting for an answer stays open, even when the mouse leaves. */
  pinned = false;
  /**
   * Hovering opens the island all the way instead of peeking (off by default).
   * The island itself folds it again once the pointer has left.
   */
  openOnHover = false;
  /** How long the pointer rests on the island before a hover opens it (Coucou 0.5.9). */
  hoverRestMs = 350;
  /** Open because of a hover, until the user clicks inside it. */
  get openedByHover(): boolean {
    return this.byHover;
  }

  private byHover = false;
  private petitHide: number | null = null;
  private homeCollapse: number | null = null;
  private greetCollapse: number | null = null;
  private hoverOpen: number | null = null;

  // ── Inputs ──────────────────────────────────────────────────────────────────

  launch() {
    this.cancelTimers();
    this.transition("coucou");
  }

  mouseEntered() {
    if (this.openOnHover && (this.state === "hidden" || this.state === "petit") && !this.pinned) {
      // A pointer passing over the island on its way somewhere opens nothing: only
      // one that rests on it. Until then the island just peeks.
      this.cancelTimers();
      if (this.state === "hidden") this.transition("petit");
      this.hoverOpen = window.setTimeout(() => {
        this.hoverOpen = null;
        if (this.state !== "petit" || this.pinned) return;
        this.byHover = true;
        this.transition("home");
      }, this.hoverRestMs);
      return;
    }
    switch (this.state) {
      case "hidden":
        this.cancelTimers();
        this.transition("petit");
        break;
      case "petit":
        this.clear("petitHide");
        break;
      case "home":
        this.clear("homeCollapse");
        break;
      case "coucou":
        this.scheduleGreetCollapse(this.greetHoverCollapseDelay);
        break;
    }
  }

  mouseLeft() {
    this.clear("hoverOpen");
    switch (this.state) {
      case "hidden":
        break;
      case "petit":
        this.schedulePetitHide();
        break;
      case "home":
        this.scheduleHomeCollapse();
        break;
      case "coucou":
        this.clear("greetCollapse");
        this.transition("petit");
        break;
    }
  }

  click() {
    this.byHover = false;
    if (this.state !== "petit") return;
    this.cancelTimers();
    this.transition("home");
  }

  /** Greeting animation finished (T.end). Doesn't override a running hover timer. */
  greetComplete() {
    if (this.state !== "coucou") return;
    if (this.greetCollapse == null) this.scheduleGreetCollapse(this.greetAutoCollapseDelay);
  }

  /** Non-alert work event: show compact from hidden. */
  reveal() {
    if (this.state !== "hidden") return;
    this.cancelTimers();
    this.transition("petit");
    this.schedulePetitHide();
  }

  /** The user clicked inside the island: a hover-opened island now stays like any open island. */
  userInteracted() {
    this.byHover = false;
  }

  /** Alert or explicit request: open straight to expanded. */
  forceHome() {
    this.byHover = false;
    this.cancelTimers();
    this.transition("home");
  }

  /// Explicit close (OK button, Escape, an alert being answered).
  forcePetit() {
    this.byHover = false;
    this.cancelTimers();
    this.transition("petit");
  }

  forceHidden() {
    this.byHover = false;
    this.cancelTimers();
    this.transition("hidden");
  }

  // ── Timers ──────────────────────────────────────────────────────────────────

  private schedulePetitHide() {
    // The compact pill stays up until Kai is paused. It does not tuck itself away.
    this.clear("petitHide");
  }

  private scheduleHomeCollapse() {
    this.clear("homeCollapse");
    if (this.pinned) return;
    this.homeCollapse = window.setTimeout(() => {
      this.homeCollapse = null;
      // An alert pinned while the countdown ran keeps the island open.
      if (this.state === "home" && !this.pinned) this.transition("petit");
    }, this.homeToPetitDelay * 1000);
  }

  private scheduleGreetCollapse(delay: number) {
    this.clear("greetCollapse");
    this.greetCollapse = window.setTimeout(() => {
      this.greetCollapse = null;
      if (this.state === "coucou") this.transition("petit");
    }, delay * 1000);
  }

  private clear(which: "petitHide" | "homeCollapse" | "greetCollapse" | "hoverOpen") {
    const id = this[which];
    if (id != null) window.clearTimeout(id);
    this[which] = null;
  }

  cancelTimers() {
    this.clear("petitHide");
    this.clear("homeCollapse");
    this.clear("greetCollapse");
    this.clear("hoverOpen");
  }

  private transition(next: FsmState) {
    if (next === this.state) return;
    const from = this.state;
    this.state = next;
    this.onTransition?.(from, next);
  }
}
