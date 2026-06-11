"use client";

import type { NodeScriptRunResult } from "@/types";
import { DatabaseCollectionEditor } from "./DatabaseCollectionEditor";
import { EditorDialog } from "./EditorDialog";
import { ScriptCollectionEditor } from "./ScriptCollectionEditor";
import { TextFieldEditor } from "./TextFieldEditor";
import { type DraftChange, type LongTextEditorTarget, type NodeEditorDraft } from "./types";

type LongTextEditorDialogProps = {
  draft: NodeEditorDraft;
  target: LongTextEditorTarget;
  scriptResults: Record<string, NodeScriptRunResult>;
  onClose: () => void;
  onDraftChange: DraftChange;
  onRunScript: (script: NodeEditorDraft["attachments"]["scripts"][number]) => void;
};

export function LongTextEditorDialog({
  draft,
  target,
  scriptResults,
  onClose,
  onDraftChange,
  onRunScript
}: LongTextEditorDialogProps) {
  if (target.kind === "summary" || target.kind === "body") {
    return (
      <EditorDialog
        title={target.kind === "summary" ? "编辑摘要" : "编辑正文"}
        onClose={onClose}
        footer={<EditorFooter onClose={onClose} />}
      >
        <TextFieldEditor field={target.kind} draft={draft} onDraftChange={onDraftChange} />
      </EditorDialog>
    );
  }

  if (target.kind === "database") {
    return (
      <EditorDialog
        title="编辑知识库"
        onClose={onClose}
        footer={<EditorFooter onClose={onClose} />}
      >
        <DatabaseCollectionEditor draft={draft} initialId={target.id} onDraftChange={onDraftChange} />
      </EditorDialog>
    );
  }

  return (
    <EditorDialog
      title="编辑脚本"
      onClose={onClose}
      footer={<EditorFooter onClose={onClose} />}
    >
      <ScriptCollectionEditor draft={draft} initialId={target.id} scriptResults={scriptResults} onDraftChange={onDraftChange} onRunScript={onRunScript} />
    </EditorDialog>
  );
}

function EditorFooter({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex justify-end">
      <button
        className="inline-flex h-10 items-center rounded-full bg-slate-900 px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
        onClick={onClose}
        type="button"
      >
        完成
      </button>
    </div>
  );
}
