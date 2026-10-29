// How much of the Claude plan is used (usage.py on the host): the plan's own
// limits when Claude Code in a terminal reports them, else Kai's own count of
// the current five-hour window from the transcripts.

import { turkish } from "./prefs";

export interface UsageWindow { used: number; resets: number }
export interface UsageSnapshot {
  limits: { five_hour?: UsageWindow; seven_day?: UsageWindow } | null;
  local: { replies: number; output: number; tokens: number; started: number; resets: number } | null;
}

const clock = (epoch: number) =>
  new Date(epoch * 1000).toLocaleTimeString(turkish() ? "tr-TR" : "en-GB", { hour: "2-digit", minute: "2-digit" });

const thousands = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}${turkish() ? " bin" : "k"}` : String(n);

/** Green, amber, red, like the plan gauge on the Mac. */
export const usageColor = (pct: number) => (pct < 50 ? "#22C55E" : pct < 80 ? "#F59E0B" : "#F4505E");

/** The higher of the two windows' percentages, or null without the plan's numbers. */
export function usagePct(u: UsageSnapshot | null): number | null {
  const l = u?.limits;
  if (!l) return null;
  const values = [l.five_hour?.used, l.seven_day?.used].filter((v): v is number => typeof v === "number");
  return values.length ? Math.max(...values) : null;
}

/** The short chip next to the session's name. */
export function usageChip(u: UsageSnapshot | null): string {
  const pct = usagePct(u);
  if (pct != null) return `%${pct}`;
  if (u?.local) return turkish() ? `${u.local.replies} cevap` : `${u.local.replies} replies`;
  return "";
}

/** The rows of the Kai pill's card: [label, detail, percentage or null]. */
export function usageRows(u: UsageSnapshot | null): [string, string, number | null][] {
  const tr = turkish();
  const rows: [string, string, number | null][] = [];
  const l = u?.limits;
  if (l?.five_hour) rows.push([tr ? "5 saatlik limit" : "5-hour limit", `%${l.five_hour.used} · ${clock(l.five_hour.resets)}`, l.five_hour.used]);
  if (l?.seven_day) rows.push([tr ? "Haftalık limit" : "Weekly limit", `%${l.seven_day.used}`, l.seven_day.used]);
  if (!rows.length && u?.local) {
    const x = u.local;
    rows.push([
      tr ? "Bu 5 saatlik pencere" : "This 5-hour window",
      tr ? `${x.replies} cevap · ${thousands(x.tokens)} token · ${clock(x.resets)}'te sıfırlanır`
        : `${x.replies} replies · ${thousands(x.tokens)} tokens · resets ${clock(x.resets)}`,
      null,
    ]);
  }
  return rows;
}
