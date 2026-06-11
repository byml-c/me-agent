"use client";

import type { DraftChange, NodeEditorDraft } from "./types";

type TextFieldEditorProps = {
  field: "summary" | "body";
  draft: NodeEditorDraft;
  onDraftChange: DraftChange;
};

export function TextFieldEditor({ field, draft, onDraftChange }: TextFieldEditorProps) {
  const value = draft[field];

  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)] gap-3 p-5">
      <div className="flex justify-end text-xs text-slate-500">{value.length} chars</div>
      <textarea
        className="min-h-0 w-full resize-none rounded-3xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-900 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
        value={value}
        onChange={(event) => onDraftChange((current) => current ? { ...current, [field]: event.target.value } : current)}
        placeholder={field === "summary" ? "输入摘要" : "输入正文"}
      />
    </div>
  );
}
