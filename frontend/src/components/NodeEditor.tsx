"use client";

import { type Dispatch, type RefObject, type SetStateAction, useEffect, useState } from "react";
import { Archive, CircleHelp, Code2, Database, Play, Plus, Save, Sparkles, Trash2, X } from "lucide-react";
import { api } from "@/api/client";
import { getNodeIcon, type NodeIconKey, type NodeIconOption } from "@/lib/nodeIcons";
import type { MeNode, NodeAttachments, NodeScriptAttachment, NodeScriptRunResult } from "@/types";

export type NodeEditorDraft = {
  title: string;
  summary: string;
  body: string;
  icon: NodeIconKey;
  attachments: NodeAttachments;
  is_workspace: boolean;
  status: MeNode["status"];
};

type NodeEditorPaneProps = {
  activeNode: MeNode | null;
  anchorId: string;
  draft: NodeEditorDraft | null;
  filteredNodeIconOptions: NodeIconOption[];
  iconPickerOpen: boolean;
  iconSearch: string;
  iconSearchRef: RefObject<HTMLInputElement | null>;
  nodeSaving: boolean;
  nodeTitleRef: RefObject<HTMLInputElement | null>;
  scriptResults: Record<string, NodeScriptRunResult>;
  onAddDatabase: () => void;
  onAddScript: () => void;
  onClose: () => void;
  onDiscard: () => void;
  onDraftChange: Dispatch<SetStateAction<NodeEditorDraft | null>>;
  onIconPickerOpenChange: Dispatch<SetStateAction<boolean>>;
  onIconSearchChange: Dispatch<SetStateAction<string>>;
  onImportDatabaseAttachment: (entryId: string, selectedFile: File | null) => void;
  onRemoveAttachment: <T extends keyof NodeAttachments>(key: T, id: string) => void;
  onRunScript: (script: NodeScriptAttachment) => void;
  onSave: () => void;
  onUpdateAttachment: <T extends keyof NodeAttachments>(key: T, id: string, changes: Partial<NodeAttachments[T][number]>) => void;
};

const SCRIPT_RUNTIME_HELP = [
  "函数: open_app(app, args=[], once=True)",
  "函数: list_node_files(), get_node_file(file_id|name), log(value)",
  "变量: NODE_ID, SCRIPT_ARGS, NODE_DATABASES, NODE_FILES, TRIGGER",
  "open_app 支持字符串参数，会自动展开 $HOME 和 ~"
].join("\n");

const ghostButtonClass = "grid h-8 w-8 place-items-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-900/20";
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
  anchorId,
  draft,
  filteredNodeIconOptions,
  iconPickerOpen,
  iconSearch,
  iconSearchRef,
  nodeSaving,
  nodeTitleRef,
  scriptResults,
  onAddDatabase,
  onAddScript,
  onClose,
  onDiscard,
  onDraftChange,
  onIconPickerOpenChange,
  onIconSearchChange,
  onImportDatabaseAttachment,
  onRemoveAttachment,
  onRunScript,
  onSave,
  onUpdateAttachment
}: NodeEditorPaneProps) {
  if (!draft) {
    return <div className="grid place-items-center p-6 text-sm text-slate-500">选择一个节点后显示属性。</div>;
  }

  return (
    <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden">
      <div className="grid min-h-0 gap-3 overflow-auto p-3">
        <section className="grid gap-3 rounded-3xl border border-slate-200 bg-white p-3">
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
          <label className="grid gap-2 text-xs font-semibold text-slate-500">
            摘要
            <textarea
              className={`${fieldClass} min-h-[clamp(58px,11vh,92px)] resize-none leading-6`}
              value={draft.summary}
              onChange={(event) => onDraftChange((current) => current ? { ...current, summary: event.target.value } : current)}
            />
          </label>
          <label className="grid gap-2 text-xs font-semibold text-slate-500">
            正文
            <textarea
              className={`${fieldClass} min-h-[120px] resize-y leading-6`}
              value={draft.body}
              onChange={(event) => onDraftChange((current) => current ? { ...current, body: event.target.value } : current)}
            />
          </label>
        </section>

        <section className="grid gap-2 rounded-3xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center justify-between gap-2 text-xs font-bold text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Database size={13} /> 知识库
            </span>
            <button className={ghostButtonClass} title="添加知识条目" onClick={onAddDatabase} type="button">
              <Plus size={13} />
            </button>
          </div>
          <div className="grid gap-2">
            {draft.attachments.databases.map((database) => (
              <div key={database.id} className="grid gap-2 rounded-2xl border border-slate-200 bg-white p-2">
                <div className="grid grid-cols-[minmax(88px,0.42fr)_minmax(0,1fr)_30px] items-center gap-1.5">
                  <input
                    className={`${smallFieldClass} h-9 rounded-xl`}
                    value={database.name}
                    placeholder="名称"
                    onChange={(event) => onUpdateAttachment("databases", database.id, { name: event.target.value })}
                  />
                  <input
                    className={`${smallFieldClass} h-9 rounded-xl`}
                    value={database.summary ?? ""}
                    placeholder="摘要（供 AI 检索，可留空由后台生成）"
                    onChange={(event) => onUpdateAttachment("databases", database.id, { summary: event.target.value, description: event.target.value })}
                  />
                  <button className={ghostButtonClass} title="移除" onClick={() => onRemoveAttachment("databases", database.id)} type="button">
                    <Trash2 size={13} />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <label className="inline-flex h-[30px] w-fit cursor-pointer items-center justify-center rounded-full border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-600 transition hover:bg-slate-50">
                    上传文件
                    <input
                      type="file"
                      hidden
                      onChange={(event) => {
                        onImportDatabaseAttachment(database.id, event.target.files?.[0] ?? null);
                        event.currentTarget.value = "";
                      }}
                    />
                  </label>
                  <span className="inline-flex h-6 items-center rounded-full bg-emerald-50 px-3 text-xs font-semibold text-emerald-700">{database.kind === "file" ? "文件" : "文本"}</span>
                  {database.kind === "file" ? (
                    <input
                      className={`${smallFieldClass} h-[30px] max-w-[180px] rounded-full px-3 py-1.5`}
                      value={database.media_type ?? ""}
                      placeholder="media type"
                      onChange={(event) => onUpdateAttachment("databases", database.id, { media_type: event.target.value })}
                    />
                  ) : null}
                </div>
                <textarea
                  className={`${fieldClass} min-h-[72px] max-h-[180px] resize-y rounded-xl text-xs leading-6`}
                  value={database.content ?? ""}
                  placeholder="输入知识正文，或上传文本文件。保存后写入后端统一向量知识库。"
                  onChange={(event) => onUpdateAttachment("databases", database.id, { content: event.target.value, kind: database.kind ?? "text" })}
                />
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-2 rounded-3xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center justify-between gap-2 text-xs font-bold text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Code2 size={13} /> 脚本
            </span>
            <div className="flex items-center gap-2">
              <div className="group relative inline-flex h-[26px] w-[26px] items-center justify-center rounded-full text-slate-500 hover:bg-slate-100" aria-label="脚本运行时帮助">
                <CircleHelp size={13} />
                <div className="absolute right-0 top-[calc(100%+8px)] w-[320px] rounded-xl bg-slate-900 px-3 py-2 text-[11px] leading-5 text-emerald-50 opacity-0 shadow-[0_14px_28px_rgba(15,23,42,0.16)] transition group-hover:opacity-100">
                  {SCRIPT_RUNTIME_HELP}
                </div>
              </div>
              <button className={ghostButtonClass} title="添加脚本" onClick={onAddScript} type="button">
                <Plus size={13} />
              </button>
            </div>
          </div>
          <div className="grid gap-2">
            {draft.attachments.scripts.map((script) => (
              <div key={script.id} className="grid gap-2 rounded-2xl border border-slate-200 bg-white p-2">
                <div className="grid grid-cols-[minmax(0,1fr)_30px_30px] items-center gap-1.5">
                  <input
                    className={`${smallFieldClass} h-9 rounded-xl`}
                    value={script.name}
                    placeholder="脚本名称"
                    onChange={(event) => onUpdateAttachment("scripts", script.id, { name: event.target.value })}
                  />
                  <button className={ghostButtonClass} title="运行脚本" onClick={() => onRunScript(script)} type="button">
                    <Play size={13} />
                  </button>
                  <button className={ghostButtonClass} title="移除" onClick={() => onRemoveAttachment("scripts", script.id)} type="button">
                    <Trash2 size={13} />
                  </button>
                </div>
                <textarea
                  className={`${fieldClass} min-h-[96px] rounded-xl font-mono text-xs leading-6`}
                  value={script.code}
                  spellCheck={false}
                  onChange={(event) => onUpdateAttachment("scripts", script.id, { code: event.target.value })}
                />
                <div className="flex flex-wrap gap-3">
                  <label className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-slate-700">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600/20"
                      checked={Boolean(script.trigger_on_enter)}
                      onChange={(event) => onUpdateAttachment("scripts", script.id, { trigger_on_enter: event.target.checked })}
                    />
                    主动进入节点时执行
                  </label>
                  <label className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-slate-700">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600/20"
                      checked={Boolean(script.trigger_on_ai_switch)}
                      onChange={(event) => onUpdateAttachment("scripts", script.id, { trigger_on_ai_switch: event.target.checked })}
                    />
                    AI 自动切换到该节点时执行
                  </label>
                </div>
                {scriptResults[script.id] ? (
                  <pre className="max-h-40 overflow-auto rounded-xl border border-slate-200 bg-slate-900 p-3 text-[11px] leading-5 text-emerald-50 whitespace-pre-wrap">
                    {formatScriptResult(scriptResults[script.id])}
                  </pre>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-2 border-t border-slate-200 p-3">
        <div className="flex items-end justify-between gap-3">
          <label className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-slate-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600/20"
              checked={draft.is_workspace}
              onChange={(event) => onDraftChange((current) => current ? { ...current, is_workspace: event.target.checked } : current)}
            />
            工作区
          </label>
          <label className="grid min-w-[132px] gap-2 text-xs font-semibold text-slate-500">
            状态
            <select
              className={`${smallFieldClass} h-10 rounded-full`}
              value={draft.status}
              onChange={(event) => onDraftChange((current) => current ? { ...current, status: event.target.value as MeNode["status"] } : current)}
            >
              <option value="active">active</option>
              <option value="dense">dense</option>
              <option value="archived">archived</option>
            </select>
          </label>
        </div>
        <div className="flex justify-between gap-3 text-[11px] text-slate-400">
          <span>updated {activeNode?.updated_at ?? "-"}</span>
          <span>access {activeNode?.access_count ?? 0}</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button className="inline-flex h-10 items-center justify-center rounded-full bg-slate-100 px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-200" onClick={onDiscard} type="button">
            放弃修改
          </button>
          <button className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-slate-900 px-4 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50" onClick={onSave} disabled={nodeSaving || !draft.title.trim()} type="button">
            <Save size={15} />
            {nodeSaving ? "保存中" : "保存"}
          </button>
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

function formatScriptResult(result: NodeScriptRunResult): string {
  const header = `status=${result.status} returncode=${result.returncode ?? "-"} trigger=${result.trigger ?? "manual_run"}`;
  const stdout = result.stdout ? `\nstdout:\n${result.stdout}` : "";
  const stderr = result.stderr ? `\nstderr:\n${result.stderr}` : "";
  return `${header}${stdout}${stderr}`;
}
