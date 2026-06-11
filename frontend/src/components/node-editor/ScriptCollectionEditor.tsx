"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import type { NodeScriptRunResult } from "@/types";
import { ScriptCodeEditor } from "./ScriptCodeEditor";
import type { DraftChange, NodeEditorDraft } from "./types";

type ScriptCollectionEditorProps = {
  draft: NodeEditorDraft;
  initialId?: string;
  scriptResults: Record<string, NodeScriptRunResult>;
  onDraftChange: DraftChange;
  onRunScript: (script: NodeEditorDraft["attachments"]["scripts"][number]) => void;
};

export function ScriptCollectionEditor({ draft, initialId, scriptResults, onDraftChange, onRunScript }: ScriptCollectionEditorProps) {
  const [selectedId, setSelectedId] = useState(initialId ?? draft.attachments.scripts[0]?.id ?? "");
  const selected = draft.attachments.scripts.find((item) => item.id === selectedId) ?? draft.attachments.scripts[0] ?? null;

  function addScript() {
    const id = newAttachmentId("script");
    onDraftChange((current) => current ? {
      ...current,
      attachments: {
        ...current.attachments,
        scripts: [...current.attachments.scripts, { id, name: "Python 脚本", language: "python", code: "print('hello from node')", description: "", trigger_on_enter: false, trigger_on_ai_switch: false, schedule_rules: [] }]
      }
    } : current);
    setSelectedId(id);
  }

  function removeScript(id: string) {
    const remaining = draft.attachments.scripts.filter((item) => item.id !== id);
    onDraftChange((current) => current ? {
      ...current,
      attachments: {
        ...current.attachments,
        scripts: current.attachments.scripts.filter((item) => item.id !== id)
      }
    } : current);
    setSelectedId(remaining[0]?.id ?? "");
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-[260px_minmax(0,1fr)] overflow-hidden">
      <aside className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3 border-r border-slate-200 bg-slate-50 p-4">
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-slate-900 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
          onClick={addScript}
          type="button"
        >
          <Plus size={15} />
          添加脚本
        </button>
        <div className="grid min-h-0 content-start gap-2 overflow-auto">
          {draft.attachments.scripts.map((script) => (
            <button
              key={script.id}
              className={`grid gap-1 rounded-2xl border p-3 text-left transition ${selected?.id === script.id ? "border-slate-900 bg-white shadow-sm" : "border-transparent bg-transparent hover:bg-white"}`}
              onClick={() => setSelectedId(script.id)}
              type="button"
            >
              <strong className="truncate text-sm font-semibold text-slate-900">{script.name || "Python 脚本"}</strong>
              <span className="truncate font-mono text-xs text-slate-500">{script.code || "空脚本"}</span>
            </button>
          ))}
        </div>
      </aside>

      {selected ? (
        <section className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3 p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-slate-900">脚本</h3>
            <button
              className="inline-flex h-9 items-center gap-2 rounded-full border border-rose-200 bg-white px-3 text-xs font-semibold text-rose-600 transition hover:bg-rose-50"
              onClick={() => removeScript(selected.id)}
              type="button"
            >
              <Trash2 size={14} />
              删除
            </button>
          </div>
          <ScriptCodeEditor script={selected} result={scriptResults[selected.id]} onDraftChange={onDraftChange} onRunScript={onRunScript} />
        </section>
      ) : (
        <div className="grid place-items-center text-sm text-slate-500">添加一个脚本开始编辑。</div>
      )}
    </div>
  );
}

function newAttachmentId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `${prefix}_${Date.now().toString(36)}`;
}
