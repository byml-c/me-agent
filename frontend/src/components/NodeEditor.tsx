"use client";

import { type Dispatch, type ReactNode, type RefObject, type SetStateAction, useEffect, useState } from "react";
import { Archive, Code2, Database, Pencil, Save, Sparkles } from "lucide-react";
import { api } from "@/api/client";
import { getNodeIcon, type NodeIconKey, type NodeIconOption } from "@/lib/nodeIcons";
import { MarkdownContent } from "@/components/MarkdownContent";
import type { MeNode, NodeScriptAttachment, NodeScriptRunResult } from "@/types";
import { LongTextEditorDialog } from "@/components/node-editor/LongTextEditorDialog";
import { type LongTextEditorTarget, type NodeEditorDraft } from "@/components/node-editor/types";
export type { NodeEditorDraft } from "@/components/node-editor/types";

type NodeEditorPaneProps = {
  activeNode: MeNode | null;
  draft: NodeEditorDraft | null;
  filteredNodeIconOptions: NodeIconOption[];
  iconPickerOpen: boolean;
  iconSearch: string;
  iconSearchRef: RefObject<HTMLInputElement | null>;
  nodeSaving: boolean;
  nodeTitleRef: RefObject<HTMLInputElement | null>;
  scriptResults: Record<string, NodeScriptRunResult>;
  onDraftChange: Dispatch<SetStateAction<NodeEditorDraft | null>>;
  onDraftCommit: (draft: NodeEditorDraft) => void;
  onIconPickerOpenChange: Dispatch<SetStateAction<boolean>>;
  onIconSearchChange: Dispatch<SetStateAction<string>>;
  onRunScript: (script: NodeScriptAttachment) => void;
};

const fieldClass = "w-full min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10";
const smallFieldClass = "w-full min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10";

type Props = {
  nodeId?: string;
  onSaved?: (node: MeNode) => void;
};

export function NodeEditor({ nodeId, onSaved }: Props) {
  const [node, setNode] = useState<MeNode | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [isWorkspace, setIsWorkspace] = useState(false);

  useEffect(() => {
    if (!nodeId) {
      setNode(null);
      setTitle("");
      setBody("");
      setIsWorkspace(false);
      return;
    }
    api.nodes.get(nodeId).then((item) => {
      setNode(item);
      setTitle(item.title);
      setBody(item.body);
      setIsWorkspace(item.is_workspace);
    }).catch(console.error);
  }, [nodeId]);

  async function save() {
    const saved = node
      ? await api.nodes.update(node.id, { title, body, is_workspace: isWorkspace })
      : await api.nodes.create({ title, body, is_workspace: isWorkspace });
    setNode(saved);
    onSaved?.(saved);
  }

  async function archive() {
    if (!node) {
      return;
    }
    const saved = await api.nodes.update(node.id, { status: "archived" });
    setNode(saved);
    onSaved?.(saved);
  }

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
      <h2 className="mb-4 text-sm font-semibold text-slate-900">{node ? "Node Detail" : "New Node"}</h2>
      <div className="grid gap-3">
        <input
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
          placeholder="标题"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <textarea
          className="min-h-32 w-full resize-y rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
          placeholder="正文"
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
        <label className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          <span>工作区节点</span>
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600/20"
            checked={isWorkspace}
            onChange={(event) => setIsWorkspace(event.target.checked)}
          />
        </label>
        {node ? (
          <div className="text-sm text-slate-500">
            访问 {node.access_count} 次，状态 {node.status}
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          <button
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full bg-emerald-700 px-4 text-sm font-medium text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={save}
            disabled={!title.trim()}
          >
            <Save size={16} />
            保存
          </button>
          {node ? (
            <>
              <button
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                onClick={() => setIsWorkspace(true)}
              >
                <Sparkles size={16} />
                升级
              </button>
              <button
                className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-rose-200 bg-white px-4 text-sm font-medium text-rose-600 transition hover:bg-rose-50"
                onClick={archive}
              >
                <Archive size={16} />
                归档
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function NodeEditorPane({
  activeNode,
  draft,
  filteredNodeIconOptions,
  iconPickerOpen,
  iconSearch,
  iconSearchRef,
  nodeSaving,
  nodeTitleRef,
  scriptResults,
  onDraftChange,
  onDraftCommit,
  onIconPickerOpenChange,
  onIconSearchChange,
  onRunScript
}: NodeEditorPaneProps) {
  const [editorTarget, setEditorTarget] = useState<LongTextEditorTarget | null>(null);

  if (!draft) {
    return <div className="grid place-items-center p-6 text-sm text-slate-500">选择一个节点后显示属性。</div>;
  }

  function updateDraftAndCommit(change: Partial<NodeEditorDraft>) {
    const nextDraft = { ...draft, ...change } as NodeEditorDraft;
    onDraftChange(nextDraft);
    onDraftCommit(nextDraft);
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {editorTarget ? (
        <LongTextEditorDialog
          draft={draft}
          target={editorTarget}
          scriptResults={scriptResults}
          onClose={() => setEditorTarget(null)}
          onDraftChange={onDraftChange}
          onRunScript={onRunScript}
        />
      ) : null}
      <div className="grid min-h-0 flex-1 grid-rows-[minmax(max-content,1fr)_auto] gap-2 overflow-auto p-3">
        <section className="grid min-h-0 grid-rows-[auto_max-content_minmax(max-content,1fr)] gap-2 rounded-3xl border border-slate-200 bg-white p-3">
          <div className="grid grid-cols-[44px_minmax(0,1fr)] items-end gap-2">
            <div className="relative z-[2]">
              <button
                className={`grid h-11 w-11 place-items-center rounded-full border transition ${iconPickerOpen ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300 hover:bg-slate-100"}`}
                type="button"
                title="选择节点图标"
                onClick={() => onIconPickerOpenChange((open) => !open)}
              >
                <NodeIconGlyph iconKey={draft.icon} />
              </button>
              {iconPickerOpen ? (
                <div className="absolute left-0 top-[calc(100%+8px)] grid w-[min(280px,calc(100vw-48px))] max-h-[304px] grid-rows-[auto_minmax(0,1fr)] gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-[0_18px_46px_rgba(25,36,30,0.16)]">
                  <input
                    ref={iconSearchRef}
                    className={smallFieldClass}
                    placeholder="搜索 icon"
                    value={iconSearch}
                    onChange={(event) => onIconSearchChange(event.target.value)}
                  />
                  <div className="grid grid-cols-2 gap-1.5 overflow-auto">
                    {filteredNodeIconOptions.map((option) => (
                      <button
                        key={option.key || "empty"}
                        className={`flex h-9 items-center gap-2 rounded-xl border px-2 text-left text-xs font-semibold transition ${draft.icon === option.key ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300 hover:bg-slate-100"}`}
                        title={option.label}
                        onClick={() => {
                          onDraftChange((current) => current ? { ...current, icon: option.key } : current);
                          onIconPickerOpenChange(false);
                          onIconSearchChange("");
                        }}
                        type="button"
                      >
                        <NodeIconGlyph iconKey={option.key} />
                        <span className="truncate">{option.label}</span>
                      </button>
                    ))}
                    {filteredNodeIconOptions.length === 0 ? <div className="col-span-2 py-3 text-center text-xs text-slate-500">没有匹配的 icon</div> : null}
                  </div>
                </div>
              ) : null}
            </div>
            <label className="grid gap-2 text-xs font-semibold text-slate-500">
              标题
              <input
                ref={nodeTitleRef}
                className={fieldClass}
                value={draft.title}
                onChange={(event) => onDraftChange((current) => current ? { ...current, title: event.target.value } : current)}
              />
            </label>
          </div>
          <ExpandableTextPreview
            label="摘要"
            value={draft.summary}
            placeholder="暂无摘要"
            onOpen={() => setEditorTarget({ kind: "summary" })}
          />
          <ExpandableTextPreview
            label="正文"
            value={draft.body}
            placeholder="暂无正文"
            markdown
            onOpen={() => setEditorTarget({ kind: "body" })}
          />
        </section>

        <div className="grid gap-2">
          <CollectionButton
            icon={<Database size={14} />}
            label="知识库"
            count={draft.attachments.databases.length}
            unit="个条目"
            onOpen={() => setEditorTarget({ kind: "database" })}
          />
          <CollectionButton
            icon={<Code2 size={14} />}
            label="脚本"
            count={draft.attachments.scripts.length}
            unit="个脚本"
            onOpen={() => setEditorTarget({ kind: "script" })}
          />
        </div>
      </div>

      <div className="grid shrink-0 gap-1 border-t border-slate-200 px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          <label className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <input
              type="checkbox"
              className="h-3.5 w-3.5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600/20"
              checked={draft.is_workspace}
              onChange={(event) => updateDraftAndCommit({ is_workspace: event.target.checked })}
            />
            工作区
          </label>
          <label className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-xs font-semibold text-slate-500">
            <span className="shrink-0">状态</span>
            <select
              className="h-7 w-[92px] rounded-full border border-slate-200 bg-slate-50 px-2 py-[3px] text-center text-xs leading-4 text-slate-900 outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
              value={draft.status}
              onChange={(event) => updateDraftAndCommit({ status: event.target.value as MeNode["status"] })}
            >
              <option value="active">active</option>
              <option value="dense">dense</option>
              <option value="archived">archived</option>
            </select>
          </label>
        </div>
        <div className="flex items-center justify-between gap-3 text-[11px] text-slate-400">
          <span className="min-w-0 truncate">updated {formatDisplayDateTime(activeNode?.updated_at)}</span>
          <span className="shrink-0">access {activeNode?.access_count ?? 0}</span>
          <span className="shrink-0 font-medium">{nodeSaving ? "保存中..." : "自动保存"}</span>
        </div>
      </div>
    </div>
  );
}

function NodeIconGlyph({ iconKey }: { iconKey: NodeIconKey }) {
  const icon = getNodeIcon(iconKey);
  if (!icon) {
    return <span className="inline-block h-0.5 w-3 rounded-full bg-current opacity-60" aria-hidden="true" />;
  }
  const path = Array.isArray(icon.icon[4]) ? icon.icon[4].join(" ") : icon.icon[4];
  return (
    <svg className="h-4 w-4 fill-current" viewBox={`0 0 ${icon.icon[0]} ${icon.icon[1]}`} aria-hidden="true">
      <path d={path} />
    </svg>
  );
}

function ExpandableTextPreview({ label, value, placeholder, markdown = false, onOpen }: { label: string; value: string; placeholder: string; markdown?: boolean; onOpen: () => void }) {
  return (
    <section className="grid min-h-0 grid-rows-[auto_minmax(max-content,1fr)] gap-1.5 text-xs font-semibold text-slate-500">
      <span>{label}</span>
      <button
        className="h-full w-full overflow-auto rounded-2xl border border-slate-200 bg-slate-50 px-2.5 py-2 text-left text-sm font-normal leading-5 text-slate-700 transition hover:border-slate-300 hover:bg-white"
        onClick={onOpen}
        type="button"
      >
        {markdown && value ? (
          <MarkdownContent content={value} className="text-sm" />
        ) : (
          <span className="block whitespace-pre-wrap">{value || placeholder}</span>
        )}
      </button>
    </section>
  );
}

function CollectionButton({ icon, label, count, unit, onOpen }: { icon: ReactNode; label: string; count: number; unit: string; onOpen: () => void }) {
  return (
    <button
      className="flex min-h-12 w-full items-center justify-between gap-3 rounded-3xl border border-slate-200 bg-slate-50 px-3 py-2 text-left transition hover:border-slate-300 hover:bg-white"
      onClick={onOpen}
      type="button"
    >
      <span className="inline-flex min-w-0 items-center gap-2 text-sm font-semibold text-slate-900">
        {icon}
        <span className="truncate">{label}</span>
      </span>
      <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500">
        {count} {unit}
        <Pencil size={13} />
      </span>
    </button>
  );
}

function formatDisplayDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}
