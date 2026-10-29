// The developer's Kai collects the ratings and wishes here.
// GET    /api/inbox            → { items: [{ id, stars, text, version, lang, at }] }
// DELETE /api/inbox?id=…&id=…  → removes the ones Kai has saved as notes.
// Both need the header x-kai-key, equal to the INBOX_KEY environment variable.

import { del, get, list } from "@vercel/blob";

function allowed(req) {
  const key = process.env.INBOX_KEY || "";
  return key.length >= 24 && req.headers["x-kai-key"] === key;
}

export default async function handler(req, res) {
  if (!allowed(req)) return res.status(401).json({ error: "key" });

  if (req.method === "GET") {
    const items = [];
    let cursor;
    do {
      const page = await list({ prefix: "feedback/", cursor, limit: 100 });
      for (const blob of page.blobs) {
        try {
          const found = await get(blob.url, { access: "private", useCache: false });
          if (!found) continue;
          const item = await new Response(found.stream).json();
          items.push({ id: blob.url, ...item });
        } catch {
          /* a broken file is skipped, not fatal */
        }
      }
      cursor = page.hasMore ? page.cursor : undefined;
    } while (cursor && items.length < 500);
    return res.status(200).json({ items });
  }

  if (req.method === "DELETE") {
    const ids = [].concat(req.query.id || []).filter((id) => typeof id === "string" && id.startsWith("https://"));
    if (ids.length) await del(ids);
    return res.status(200).json({ removed: ids.length });
  }

  res.setHeader("Allow", "GET, DELETE");
  return res.status(405).json({ error: "method" });
}
