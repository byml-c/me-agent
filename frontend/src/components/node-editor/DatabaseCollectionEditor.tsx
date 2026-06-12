"use client";

import { useMemo, useState } from "react";
import { Download, Plus, Trash2 } from "lucide-react";
import { api } from "@/api/client";
import type { NodeDatabaseAttachment } from "@/types";
import type { DraftChange, NodeEditorDraft } from "./types";

type DatabaseCollectionEditorProps = {
  draft: NodeEditorDraft;
  initialId?: string;
  onDraftChange: DraftChange;
};

export function DatabaseCollectionEditor({ draft, initialId, onDraftChange }: DatabaseCollectionEditorProps) {
  const [selectedId, setSelectedId] = useState(initialId ?? draft.attachments.databases[0]?.id ?? "");
  const [summarizingIds, setSummarizingIds] = useState<Set<string>>(new Set());
  const selected = useMemo(
    () => draft.attachments.databases.find((item) => item.id === selectedId) ?? draft.attachments.databases[0] ?? null,
    [draft.attachments.databases, selectedId]
  );

  function addDatabase() {
    const id = newAttachmentId("entry");
    onDraftChange((current) => current ? {
      ...current,
      attachments: {
        ...current.attachments,
        databases: [...current.attachments.databases, { id, kind: "text", name: "知识条目", content: "", summary: "" }]
      }
    } : current);
    setSelectedId(id);
  }

  function removeDatabase(id: string) {
    const remaining = draft.attachments.databases.filter((item) => item.id !== id);
    onDraftChange((current) => current ? {
      ...current,
      attachments: {
        ...current.attachments,
        databases: current.attachments.databases.filter((item) => item.id !== id)
      }
    } : current);
    if (selectedId === id) {
      setSelectedId(remaining[0]?.id ?? "");
    }
  }

  function updateDatabase(id: string, changes: Partial<NodeDatabaseAttachment>) {
    onDraftChange((current) => current ? {
      ...current,
      attachments: {
        ...current.attachments,
        databases: current.attachments.databases.map((item) => (item.id === id ? { ...item, ...changes } : item))
      }
    } : current);
  }

  async function importFile(database: NodeDatabaseAttachment, selectedFile: File | null) {
    if (!selectedFile) {
      return;
    }
    updateDatabase(database.id, {
      kind: "file",
      name: database.name || selectedFile.name,
      path: selectedFile.name,
      media_type: selectedFile.type || "text/plain",
      content: "",
      summary: "正在生成摘要...",
      description: "正在生成摘要..."
    });
    setSummarizingIds((current) => new Set(current).add(database.id));
    try {
      const uploaded = await api.files.upload(selectedFile, {
        description: database.summary || database.description
      });
      updateDatabase(database.id, {
        entry_id: undefined,
        file_id: uploaded.id,
        kind: "file",
        name: uploaded.name,
        path: uploaded.source_path || uploaded.name,
        media_type: uploaded.media_type || selectedFile.type || "",
        content: uploaded.content || "",
        summary: uploaded.summary || uploaded.description || "",
        description: uploaded.summary || uploaded.description || "",
        download_url: uploaded.download_url || api.files.downloadUrl(uploaded.id),
        size_bytes: uploaded.size_bytes,
        text_extracted: uploaded.text_extracted
      });
      setSummarizingIds((current) => {
        const next = new Set(current);
        next.delete(database.id);
        return next;
      });
    } catch (error) {
      console.error(error);
      updateDatabase(database.id, { summary: database.summary || "", description: database.description || "" });
      setSummarizingIds((current) => {
        const next = new Set(current);
        next.delete(database.id);
        return next;
      });
    }
  }

  async function pollEntrySummary(databaseId: string, entryId: string, initialSummary: string) {
    for (let attempt = 0; attempt < 8; attempt += 1) {
      await delay(1200);
      try {
        const fresh = await api.library.getEntry(entryId);
        const nextSummary = fresh.summary || fresh.description || "";
        if (nextSummary && nextSummary !== initialSummary) {
          updateDatabase(databaseId, { summary: nextSummary, description: nextSummary });
          break;
        }
      } catch (error) {
        console.error(error);
        break;
      }
    }
    setSummarizingIds((current) => {
      const next = new Set(current);
      next.delete(databaseId);
      return next;
    });
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-[260px_minmax(0,1fr)] overflow-hidden">
      <aside className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3 border-r border-slate-200 bg-slate-50 p-4">
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-slate-900 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
          onClick={addDatabase}
          type="button"
        >
          <Plus size={15} />
          添加知识条目
        </button>
        <div className="grid min-h-0 content-start gap-2 overflow-auto">
          {draft.attachments.databases.map((database) => (
            <button
              key={database.id}
              className={`grid gap-1 rounded-2xl border p-3 text-left transition ${selected?.id === database.id ? "border-slate-900 bg-white shadow-sm" : "border-transparent bg-transparent hover:bg-white"}`}
              onClick={() => setSelectedId(database.id)}
              type="button"
            >
              <strong className="truncate text-sm font-semibold text-slate-900">{database.name || "知识条目"}</strong>
              <span className="line-clamp-2 text-xs leading-5 text-slate-500">{database.summary || database.content || "空内容"}</span>
            </button>
          ))}
        </div>
      </aside>

      {selected ? (
        <section className="grid min-h-0 grid-rows-[auto_auto_auto_auto_minmax(0,1fr)] gap-3 p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-slate-900">知识条目</h3>
            <button
              className="inline-flex h-9 items-center gap-2 rounded-full border border-rose-200 bg-white px-3 text-xs font-semibold text-rose-600 transition hover:bg-rose-50"
              onClick={() => removeDatabase(selected.id)}
              type="button"
            >
              <Trash2 size={14} />
              删除
            </button>
          </div>
          <label className="grid gap-2 text-xs font-semibold text-slate-500">
            名称
            <input
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
              value={selected.name}
              onChange={(event) => updateDatabase(selected.id, { name: event.target.value })}
            />
          </label>
          <label className="grid gap-2 text-xs font-semibold text-slate-500">
            摘要
            <textarea
              className="min-h-24 w-full resize-none rounded-3xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-900 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
              value={selected.summary ?? ""}
              onChange={(event) => updateDatabase(selected.id, { summary: event.target.value, description: event.target.value })}
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex h-9 cursor-pointer items-center rounded-full border border-slate-200 bg-white px-4 text-xs font-semibold text-slate-600 transition hover:bg-slate-50">
              上传文件
              <input
                type="file"
                hidden
                onChange={(event) => {
                  void importFile(selected, event.target.files?.[0] ?? null);
                  event.currentTarget.value = "";
                }}
              />
            </label>
            <span className="inline-flex h-8 items-center rounded-full bg-emerald-50 px-3 text-xs font-semibold text-emerald-700">{selected.kind === "file" ? "文件" : "文本"}</span>
            {summarizingIds.has(selected.id) ? <span className="text-xs font-semibold text-amber-600">正在生成摘要...</span> : null}
            {selected.kind === "file" && selected.file_id ? (
              <a
                className="inline-flex h-9 items-center gap-2 rounded-full border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
                href={selected.download_url || api.files.downloadUrl(selected.file_id)}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={14} />
                下载原文件
              </a>
            ) : null}
            <span className="ml-auto text-xs text-slate-400">{formatAttachmentSize(selected)}</span>
          </div>
          {selected.kind === "file" && selected.text_extracted === false ? (
            <div className="min-h-0 rounded-3xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-600">
              <p className="font-semibold text-slate-800">非文本文件</p>
              <p>编辑页只保留摘要和元数据。需要完整内容时，请下载原文件访问。</p>
              <p className="mt-2 text-xs text-slate-400">{selected.media_type || "unknown"} · {formatBytes(selected.size_bytes ?? 0)}</p>
            </div>
          ) : (
            <textarea
              className="min-h-0 w-full resize-none rounded-3xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-7 text-slate-900 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
              value={selected.content ?? ""}
              onChange={(event) => updateDatabase(selected.id, { content: event.target.value, kind: selected.kind ?? "text" })}
              placeholder="输入知识正文，或上传文本文件。"
            />
          )}
        </section>
      ) : (
        <div className="grid place-items-center text-sm text-slate-500">添加一个知识条目开始编辑。</div>
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

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatAttachmentSize(item: NodeDatabaseAttachment) {
  if (item.kind === "file") {
    return `${formatBytes(item.size_bytes ?? 0)}${item.text_extracted === false ? " · summary only" : ""}`;
  }
  return `${(item.content ?? "").length} chars`;
}

function formatBytes(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
