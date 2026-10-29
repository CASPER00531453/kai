// What Claude Code is doing to the files right now, kept for the code view.
// Fed from the hook events: the tool's input when it starts, and the real patch
// (with line numbers and context) once it has run.

import { State } from "./state";

export interface CodeLine {
  no: number | null;
  kind: "ctx" | "del" | "add";
  text: string;
}

export interface CodeStep {
  tool: string;
  state: "active" | "done" | "failed";
}

interface Hunk {
  oldStart?: number;
  newStart?: number;
  lines?: string[];
}

const MAX_LINES = 60;
const MAX_STEPS = 3;

class Feed {
  /** File name for the tab, e.g. "invoice.ts". Empty until a tool touches something. */
  file = "";
  path = "";
  lines: CodeLine[] = [];
  steps: CodeStep[] = [];
  finished = false;
  /** Goes up with every new document, so the view knows to type it out again. */
  stamp = 0;
  /** True once the tool has run and `lines` is the real patch. */
  settled = false;
}

export const CodeFeed = new Feed();

/** One file the turn changed, for the finished card: lines added and removed. */
export interface TurnFile { path: string; name: string; added: number; removed: number }

/** What the current turn (prompt to stop) did to the files, and when it started. */
export const Turn = {
  files: new Map<string, TurnFile>(),
  startedAt: Date.now(),
  /** Paths the running edit tools are writing, to credit when their patch lands. */
  pending: [] as { tool: string; path: string; added: number }[],
};

function credit(path: string, added: number, removed: number) {
  if (!path || (!added && !removed)) return;
  const file = Turn.files.get(path) ?? { path, name: path.split(/[\\/]/).pop() || path, added: 0, removed: 0 };
  file.added += added;
  file.removed += removed;
  Turn.files.set(path, file);
}

const text = (value: unknown) => (typeof value === "string" ? value : "");
const split = (value: string) => value.replace(/\r/g, "").split("\n");

function show(path: string, lines: CodeLine[]) {
  CodeFeed.path = path;
  CodeFeed.file = path.split(/[\\/]/).pop() || path;
  CodeFeed.lines = lines.slice(0, MAX_LINES);
  CodeFeed.settled = false;
  CodeFeed.stamp += 1;
}

function change(before: string, after: string): CodeLine[] {
  const out: CodeLine[] = [];
  if (before) split(before).forEach((line, i) => out.push({ no: i + 1, kind: "del", text: line }));
  if (after) split(after).forEach((line, i) => out.push({ no: i + 1, kind: "add", text: line }));
  return out;
}

export function codeToolStart(tool: string, input: Record<string, unknown>) {
  CodeFeed.finished = false;
  CodeFeed.steps.push({ tool, state: "active" });
  CodeFeed.steps = CodeFeed.steps.slice(-MAX_STEPS);

  const path = text(input.file_path) || text(input.notebook_path);
  if (path && ["Edit", "MultiEdit", "Write", "NotebookEdit"].includes(tool)) {
    // A new file has no patch: its lines are all added.
    Turn.pending.push({ tool, path, added: tool === "Write" ? split(text(input.content)).length : 0 });
  }
  if (tool === "Edit" && path) {
    show(path, change(text(input.old_string), text(input.new_string)));
  } else if (tool === "MultiEdit" && path && Array.isArray(input.edits)) {
    const lines: CodeLine[] = [];
    for (const edit of input.edits as Record<string, unknown>[]) {
      lines.push(...change(text(edit.old_string), text(edit.new_string)));
    }
    show(path, lines);
  } else if (tool === "Write" && path) {
    show(path, change("", text(input.content)));
  } else if ((tool === "Bash" || tool === "PowerShell") && text(input.command)) {
    show("terminal", split(text(input.command)).map((line, i) => ({ no: null, kind: "ctx", text: (i ? "  " : "$ ") + line })));
  }
  State.notify();
}

export function codeToolEnd(tool: string, patch: unknown, failed: boolean) {
  for (let i = CodeFeed.steps.length - 1; i >= 0; i--) {
    const step = CodeFeed.steps[i];
    if (step.state === "active" && step.tool === tool) {
      step.state = failed ? "failed" : "done";
      break;
    }
  }
  // Credit the file this tool was writing with what its patch changed.
  const at = Turn.pending.findIndex((p) => p.tool === tool);
  const pending = at >= 0 ? Turn.pending.splice(at, 1)[0] : null;
  if (pending && !failed) {
    if (Array.isArray(patch) && patch.length > 0) {
      let added = 0;
      let removed = 0;
      for (const hunk of patch as Hunk[]) {
        for (const raw of hunk.lines ?? []) {
          if (raw.startsWith("+")) added++;
          else if (raw.startsWith("-")) removed++;
        }
      }
      credit(pending.path, added, removed);
    } else {
      credit(pending.path, pending.added, 0);
    }
  }
  if (Array.isArray(patch) && patch.length > 0) {
    const lines: CodeLine[] = [];
    (patch as Hunk[]).forEach((hunk, index) => {
      if (index > 0) lines.push({ no: null, kind: "ctx", text: "⋯" });
      let before = Number(hunk.oldStart ?? 1);
      let after = Number(hunk.newStart ?? 1);
      for (const raw of hunk.lines ?? []) {
        const body = raw.slice(1);
        if (raw.startsWith("-")) lines.push({ no: before++, kind: "del", text: body });
        else if (raw.startsWith("+")) lines.push({ no: after++, kind: "add", text: body });
        else {
          lines.push({ no: after++, kind: "ctx", text: body });
          before++;
        }
      }
    });
    CodeFeed.lines = lines.slice(0, MAX_LINES);
  }
  CodeFeed.settled = true;
  State.notify();
}

export function codePrompt() {
  Turn.files.clear();
  Turn.pending = [];
  Turn.startedAt = Date.now();
  CodeFeed.steps = [];
  CodeFeed.finished = false;
  State.notify();
}

export function codeStop() {
  for (const step of CodeFeed.steps) if (step.state === "active") step.state = "done";
  CodeFeed.finished = true;
  CodeFeed.settled = true;
  State.notify();
}
