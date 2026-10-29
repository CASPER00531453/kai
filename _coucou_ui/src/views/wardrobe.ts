// Wardrobe view. Opened with a right-click on the bot or from Settings. Resting
// the pointer on a button tries the outfit on; a click keeps it.

import { h } from "./dom";
import { prefs, setPref, turkish } from "../core/prefs";
import { State } from "../core/state";
import { drawWardrobeIcon } from "../mochi/outfits";
import {
  WARDROBE, autoBadge, outfitLabel, parseOutfit, resolveOutfit, seasonalOutfit, wardrobeHeader, wardrobeTitle,
  type Outfit, type OutfitSelection,
} from "../mochi/wardrobe";
import { parseMascot } from "../mochi/mascots";
import type { ViewHost } from "./views";

const ICON = 28;

export function buildWardrobe(): ViewHost {
  const title = h("span", { class: "wardrobe-title" });
  const note = h("span", { class: "wardrobe-note" });
  const grid = h("div", { class: "wardrobe-grid" });
  const el = h(
    "div",
    { class: "view wardrobe" },
    h("div", { class: "card" }, h("div", { class: "stack wardrobe-stack" }, h("div", { class: "wardrobe-head" }, title, note), grid)),
  );

  let hovered: OutfitSelection | null = null;
  let drawnSeason: Outfit | null = null;
  let drawnTurkish = turkish();
  let drawnMascot = "";
  const items = new Map<OutfitSelection, { button: HTMLButtonElement; canvas: HTMLCanvasElement }>();

  const current = () => parseOutfit(prefs()?.outfit ?? State.settings.mochiOutfit);
  const updateNote = () => {
    note.textContent = wardrobeHeader(hovered, current(), new Date());
  };

  for (const sel of WARDROBE) {
    const canvas = h("canvas");
    const button = h("button", { class: "wardrobe-item" }, canvas);
    button.addEventListener("mouseenter", () => {
      hovered = sel;
      State.wardrobePreview = resolveOutfit(sel, new Date());
      State.lastActivity = performance.now();
      updateNote();
    });
    button.addEventListener("mouseleave", () => {
      if (hovered !== sel) return;
      hovered = null;
      State.wardrobePreview = null;
      updateNote();
    });
    button.addEventListener("click", () => {
      State.settings.mochiOutfit = sel;
      void setPref("outfit", sel);
    });
    items.set(sel, { button, canvas });
    grid.append(button);
  }

  /** Icons are drawn once; only "auto" changes, with the season and its badge's language. */
  const drawIcons = () => {
    const season = seasonalOutfit(new Date());
    const mascot = parseMascot(prefs()?.mascot);
    if (season === drawnSeason && drawnTurkish === turkish() && drawnMascot === mascot) return;
    // A new mascot wears every outfit differently: all the buttons are redrawn.
    const first = drawnSeason == null || drawnMascot !== mascot;
    drawnMascot = mascot;
    drawnSeason = season;
    drawnTurkish = turkish();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    for (const [sel, { canvas }] of items) {
      if (!first && sel !== "auto") continue;
      canvas.width = Math.round(ICON * dpr);
      canvas.height = Math.round(ICON * dpr);
      const ctx = canvas.getContext("2d");
      if (!ctx) continue;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawWardrobeIcon(ctx, ICON, sel, season, autoBadge(), mascot);
    }
  };

  return {
    el,
    sync() {
      drawIcons();
      // The island drops the preview when the view closes: so does the hover.
      if (State.wardrobePreview == null) hovered = null;
      title.textContent = wardrobeTitle();
      const chosen = current();
      for (const [sel, { button }] of items) {
        button.classList.toggle("on", sel === chosen);
        button.title = outfitLabel(sel);
      }
      updateNote();
    },
  };
}
