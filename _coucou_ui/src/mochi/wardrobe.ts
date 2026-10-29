// The wardrobe — the pure logic. What the bot wears is picked in the wardrobe
// view (right-click on the bot, or Settings) and kept by the host as `outfit`.
// The drawing lives in ./outfits.ts.

import { turkish } from "../core/prefs";

/** Every outfit the drawing knows, plus "auto" (dress for the season) and "none". */
export const OUTFIT_SELECTIONS = [
  "auto", "none", "partyHat", "beanie", "crown", "sunglasses", "roundGlasses",
  "bow", "scarf", "witchHat", "pumpkin", "santaHat", "bunnyEars",
  "fez", "gradCap", "teamScarf",
] as const;

/** What can be stored in the preferences. */
export type OutfitSelection = (typeof OUTFIT_SELECTIONS)[number];

/** What is actually worn: a selection with "auto" resolved. */
export type Outfit = Exclude<OutfitSelection, "auto">;

/**
 * The order of the wardrobe. The pumpkin is left out: it recolours the whole
 * body, and Kai already has a pumpkin among its accessories.
 */
export const WARDROBE: OutfitSelection[] = OUTFIT_SELECTIONS.filter((s) => s !== "pumpkin");

export const DEFAULT_OUTFIT: OutfitSelection = "none";

// ── User-visible strings ──────────────────────────────────────────────────────

/** Each name as [Türkçe, English]. */
const NAMES: Record<OutfitSelection, [string, string]> = {
  auto: ["Otomatik (mevsime göre)", "Auto (seasons)"],
  none: ["Yok", "None"],
  partyHat: ["Parti şapkası", "Party hat"],
  beanie: ["Bere", "Beanie"],
  crown: ["Taç", "Crown"],
  sunglasses: ["Güneş gözlüğü", "Sunglasses"],
  roundGlasses: ["Yuvarlak gözlük", "Round glasses"],
  bow: ["Papyon", "Bow"],
  scarf: ["Atkı", "Scarf"],
  witchHat: ["Cadı şapkası", "Witch hat"],
  pumpkin: ["Balkabağı", "Pumpkin"],
  santaHat: ["Noel şapkası", "Santa hat"],
  bunnyEars: ["Tavşan kulakları", "Bunny ears"],
  fez: ["Fes", "Fez"],
  gradCap: ["Mezuniyet kepi", "Graduation cap"],
  teamScarf: ["Taraftar atkısı", "Supporter's scarf"],
};

/**
 * Ramazan and Kurban Bayramı, first to last day, as Turkey's Diyanet calendar
 * gives them ([month, day] pairs; the lunar dates move about eleven days a year).
 */
const BAYRAMS: Record<number, [number, number, number, number][]> = {
  2026: [[3, 20, 3, 22], [5, 27, 5, 30]],
  2027: [[3, 9, 3, 11], [5, 16, 5, 19]],
  2028: [[2, 26, 2, 28], [5, 4, 5, 7]],
  2029: [[2, 14, 2, 16], [4, 23, 4, 26]],
  2030: [[2, 4, 2, 6], [4, 13, 4, 16]],
};

function isBayram(month: number, day: number, year: number): boolean {
  return (BAYRAMS[year] ?? []).some(([m0, d0, m1, d1]) => {
    const v = month * 100 + day;
    return v >= m0 * 100 + d0 && v <= m1 * 100 + d1;
  });
}

export const outfitLabel = (selection: OutfitSelection) => NAMES[selection][turkish() ? 0 : 1];
export const wardrobeTitle = () => (turkish() ? "Gardırop" : "Wardrobe");
export const autoBadge = () => (turkish() ? "OTO" : "AUTO");

// ── Logic ─────────────────────────────────────────────────────────────────────

const SELECTION_SET: ReadonlySet<string> = new Set(OUTFIT_SELECTIONS);

/** A stored preference → a selection. Anything unknown means the default. */
export function parseOutfit(raw: unknown): OutfitSelection {
  return typeof raw === "string" && SELECTION_SET.has(raw) ? (raw as OutfitSelection) : DEFAULT_OUTFIT;
}

/** Easter Sunday of `year` (Meeus/Jones/Butcher), as [month 1–12, day]. */
export function easterDate(year: number): [number, number] {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return [month, day];
}

const DAY_MS = 86_400_000;

/**
 * The seasonal outfit for `date`, read in the user's local calendar.
 * Priority: party hat > Santa hat > witch hat > bunny ears > sunglasses > none.
 */
export function seasonalOutfit(date: Date): Outfit {
  const day = date.getDate();
  const month = date.getMonth() + 1;
  const year = date.getFullYear();

  // Dec 31 – Jan 2
  if ((month === 12 && day === 31) || (month === 1 && day <= 2)) return "partyHat";
  // Ramazan and Kurban Bayramı: a fez.
  if (isBayram(month, day, year)) return "fez";
  // Dec 1–26
  if (month === 12 && day <= 26) return "santaHat";
  // Oct 1 – Nov 1
  if (month === 10 || (month === 11 && day === 1)) return "witchHat";
  // Two days before Easter to the day after. Calendar days counted in UTC so a
  // daylight-saving change in between can't shift the count.
  const [em, ed] = easterDate(year);
  const delta = Math.round((Date.UTC(year, month - 1, day) - Date.UTC(year, em - 1, ed)) / DAY_MS);
  if (delta >= -2 && delta <= 1) return "bunnyEars";
  // Jun 21 – Aug 31
  if ((month === 6 && day >= 21) || month === 7 || month === 8) return "sunglasses";
  return "none";
}

/** "auto" → the season's outfit; anything else is worn as chosen. */
export function resolveOutfit(selection: OutfitSelection, date: Date): Outfit {
  return selection === "auto" ? seasonalOutfit(date) : selection;
}

/** The grey text at the right of the wardrobe header: the hovered outfit, otherwise the current choice. */
export function wardrobeHeader(hovered: OutfitSelection | null, selection: OutfitSelection, date: Date): string {
  const shown = hovered ?? selection;
  if (shown !== "auto") return outfitLabel(shown);
  const season = outfitLabel(seasonalOutfit(date));
  return turkish() ? `Otomatik · ${season}` : `Auto · ${season}`;
}

/** Same as resolveOutfit, remembered for the day — it is asked every frame. */
export class SeasonCache {
  private key = "";
  private value: Outfit = "none";

  get(selection: OutfitSelection, date = new Date()): Outfit {
    if (selection !== "auto") return selection;
    const key = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
    if (key !== this.key) {
      this.key = key;
      this.value = seasonalOutfit(date);
    }
    return this.value;
  }
}
