// Notetaker: record a call, see the words live, then read the notes.

import { h } from "../views/dom";
import { Api, type Note, type RecorderStatus } from "./api";
import type { Ctx } from "./flowpages";
import { modelsGrid } from "./flowpages";
import { button, card, clock, keycap, L, toast, when } from "./ui";

let openNote: string | null = null;

export function notesPage(ctx: Ctx, list: { id: string; title: string; started: number; seconds: number }[]): HTMLElement {
  const rec = ctx.state.status.recorder;
  const page = h("div", { class: "a-page" });
  page.append(recorderCard(ctx, rec));
  if (openNote) {
    const holder = h("div", {});
    page.append(holder);
    void Api.note(openNote).then((note) => {
      if (note) holder.append(noteView(ctx, note));
    });
    return page;
  }
  page.append(
    card(
      L("Notların", "Your notes"),
      list.length
        ? h("div", { class: "a-list" }, ...list.map((n) => {
            const r = h("button", { class: "a-list-row link" }, h("b", { text: n.title || n.id }), h("span", { class: "a-muted", text: `${when(n.started)} · ${Math.max(1, Math.round(n.seconds / 60))} ${L("dk", "min")}` }));
            r.addEventListener("click", () => { openNote = n.id; ctx.go("notes"); });
            return r;
          }))
        : h("p", { class: "a-muted", text: L("Henüz not yok. Bir görüşmede Kaydet'e bas.", "No notes yet. Press Record in a call.") }),
    ),
    card(L("Kimin konuştuğunu ayırmak için", "To tell speakers apart"), modelsGrid(ctx, ["speakers"])),
  );
  return page;
}

function meter(level: number, label: string, color: string): HTMLElement {
  return h("div", { class: "a-meter" }, h("span", { text: label }), h("div", {}, h("i", { style: `width:${Math.min(100, level * 100)}%;background:${color}` })));
}

function recorderCard(ctx: Ctx, rec?: RecorderStatus): HTMLElement {
  const on = Boolean(rec?.recording);
  const busy = Boolean(rec?.processing);
  const big = h("button", { class: `a-record${on ? " on" : ""}`, disabled: busy ? "true" : undefined },
    h("i", {}),
    h("span", { text: busy ? L("Notlar yazılıyor…", "Writing the notes…") : on ? L("Durdur", "Stop") : L("Görüşmeyi kaydet", "Record a call") }),
  );
  big.addEventListener("click", async () => {
    await Api.record(!on);
    await ctx.refresh();
  });
  const live = h("div", { class: "a-live" }, ...(rec?.live ?? []).slice(-12).map((l) => h("p", {}, h("b", { class: l.who === "me" ? "me" : "them", text: l.who === "me" ? L("Sen", "You") : L("Karşı taraf", "Them") }), " ", l.text)));
  return card(
    null,
    h("div", { class: "a-rec-head" },
      big,
      h("div", { class: "a-rec-side" },
        on ? h("div", { class: "a-rec-clock", text: clock(rec?.seconds ?? 0) }) : h("p", { class: "a-muted", text: L("Mikrofonunu ve bilgisayardan çıkan sesi kaydeder; görüşmeye bot girmez. Bitince konuşmacılara göre döküm, özet, önemli noktalar ve yapılacaklar yazılır, ses silinir.", "Records your mic and what the computer plays; no bot joins. Afterwards: a transcript per speaker, a summary, key points and to-dos; the audio is deleted.") }),
        on ? h("div", {}, meter(rec?.mic ?? 0, L("Sen", "You"), "#35b8ff"), meter(rec?.system ?? 0, L("Bilgisayar", "Computer"), "#c792ea")) : null,
        h("p", { class: "a-muted small" }, keycap("Alt", "Shift", "N"), L(" ile her yerden başlat ve durdur · Kayıt yaptığını karşı tarafa söyle", " starts and stops it from anywhere · Tell the others you record")),
      ),
    ),
    rec?.error ? h("p", { class: "a-error", text: rec.error }) : null,
    on && rec?.live?.length ? live : null,
  );
}

function noteView(ctx: Ctx, note: Note): HTMLElement {
  const back = button(L("← Notlar", "← Notes"), () => { openNote = null; ctx.go("notes"); }, "ghost");
  const copy = button(L("Markdown olarak kopyala", "Copy as Markdown"), async () => {
    const md = await Api.noteMarkdown(note.id);
    await navigator.clipboard.writeText(md);
    toast(L("Kopyalandı", "Copied"));
  }, "ghost");
  const save = button(L("Dışa aktar", "Export"), async () => {
    const path = await Api.noteExport(note.id);
    if (path) toast(L("Kaydedildi", "Saved"));
  }, "ghost");
  const del = button(L("Sil", "Delete"), async () => {
    await Api.noteDelete(note.id);
    openNote = null;
    ctx.go("notes");
  }, "danger");
  const names = note.speakers || {};
  const people = h("div", { class: "a-people" }, ...Object.entries(names).map(([n, name]) => {
    const field = h("input", { class: "a-input", value: name }) as HTMLInputElement;
    field.value = name;
    field.addEventListener("change", async () => {
      await Api.noteRename(note.id, n, field.value);
      ctx.go("notes");
    });
    return h("label", { class: `a-person p${n}` }, h("i", {}), field);
  }));
  const transcript = h("div", { class: "a-transcript" }, ...note.transcript.map((l) =>
    h("p", { class: `p${l.speaker}` }, h("b", { text: names[String(l.speaker)] ?? `#${l.speaker}` }), h("span", { class: "a-muted", text: ` ${clock(l.start)} ` }), l.text),
  ));
  return h(
    "div",
    { class: "a-note" },
    h("div", { class: "a-inline" }, back, h("div", { class: "grow" }), copy, save, del),
    card(
      null,
      h("h2", { class: "a-note-title", text: note.title || note.id }),
      h("p", { class: "a-muted", text: `${when(note.started)} · ${clock(note.seconds)}` }),
      note.summary ? h("p", { class: "a-summary", text: note.summary }) : null,
      note.key_points.length ? h("div", {}, h("h4", { text: L("Önemli noktalar", "Key points") }), h("ul", {}, ...note.key_points.map((p) => h("li", { text: p })))) : null,
      note.todos.length ? h("div", {}, h("h4", { text: L("Yapılacaklar", "To-dos") }), h("ul", { class: "a-todos" }, ...note.todos.map((p) => h("li", { text: p })))) : null,
    ),
    card(L("Konuşanlar", "Speakers"), people),
    card(L("Döküm", "Transcript"), transcript),
  );
}
