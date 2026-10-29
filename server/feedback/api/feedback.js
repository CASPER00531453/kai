// POST /api/feedback — a rating and a wish sent from Kai's settings, or a crash
// report the user agreed to send.
// Rating: { stars: 1..5, text, version, lang }.
// Crash:  { kind: "crash", text: the error, version, lang }.
// Each one is kept as its own small JSON file in the Blob store until the
// developer's Kai takes it (api/inbox.js). Nothing else about the sender is kept.

import { put } from "@vercel/blob";

const MAX_TEXT = 2000;
const MAX_CRASH = 4000;

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "method" });
  }
  const body = typeof req.body === "object" && req.body ? req.body : {};
  const crash = body.kind === "crash";
  const stars = crash ? 0 : Number(body.stars);
  const text = typeof body.text === "string" ? body.text.trim().slice(0, crash ? MAX_CRASH : MAX_TEXT) : "";
  if (!crash && (!Number.isInteger(stars) || stars < 1 || stars > 5)) return res.status(400).json({ error: "stars" });
  if (crash && !text) return res.status(400).json({ error: "text" });
  const item = {
    kind: crash ? "crash" : "rating",
    stars,
    text,
    version: String(body.version || "").slice(0, 20),
    lang: String(body.lang || "").slice(0, 8),
    at: Date.now(),
  };
  await put(`feedback/${item.at}.json`, JSON.stringify(item), {
    // Private: nobody reads them by URL, only the inbox with the store's token.
    access: "private",
    contentType: "application/json",
    addRandomSuffix: true,
  });
  return res.status(200).json({ ok: true });
}
