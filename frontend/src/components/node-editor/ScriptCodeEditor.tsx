"use client";

import Editor from "react-simple-code-editor";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prism-themes/themes/prism-dracula.css";
import type { NodeScriptAttachment, NodeScriptRunResult, NodeScriptScheduleRule } from "@/types";
import type { DraftChange } from "./types";

type ScriptCodeEditorProps = {
  script: NodeScriptAttachment;
  result?: NodeScriptRunResult;
  onDraftChange: DraftChange;
  onRunScript: (script: NodeScriptAttachment) => void;
};

export function ScriptCodeEditor({ script, result, onDraftChange, onRunScript }: ScriptCodeEditorProps) {
  const scheduleRules = script.schedule_rules ?? [];
  const scheduleEnabled = scheduleRules.length > 0;

  function update(changes: Partial<NodeScriptAttachment>) {
    onDraftChange((draft) => draft ? {
      ...draft,
      attachments: {
        ...draft.attachments,
        scripts: draft.attachments.scripts.map((item) => (item.id === script.id ? { ...item, ...changes } : item))
      }
    } : draft);
  }

  function updateScheduleRule(id: string, changes: Partial<NodeScriptScheduleRule>) {
    update({
      schedule_rules: scheduleRules.map((rule) => {
        if (rule.id !== id) {
          return rule;
        }
        const nextRule = { ...rule, ...changes };
        return nextRule.kind === "weekly" ? nextRule : { id: nextRule.id, kind: "daily", time: nextRule.time };
      })
    });
  }

  function addScheduleRule(kind: NodeScriptScheduleRule["kind"] = "daily") {
    update({
      schedule_rules: [
        ...scheduleRules,
        {
          id: newScheduleRuleId(),
          kind,
          time: "09:00",
          weekday: kind === "weekly" ? 1 : undefined
        }
      ]
    });
  }

  function removeScheduleRule(id: string) {
    update({ schedule_rules: scheduleRules.filter((rule) => rule.id !== id) });
  }

  return (
    <div className="grid h-full grid-rows-[auto_minmax(0,1fr)_auto] gap-3">
      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
        <label className="grid gap-2 text-xs font-semibold text-slate-500">
          <span className="flex items-center gap-1.5">
            脚本名称
            <ScriptEnvironmentHelp />
          </span>
          <input
            className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 outline-none focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
            value={script.name}
            onChange={(event) => update({ name: event.target.value })}
          />
        </label>
        <button
          className="self-end rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
          onClick={() => onRunScript(script)}
          type="button"
        >
          运行脚本
        </button>
      </div>

      <Editor
        className="min-h-0 overflow-auto rounded-3xl border border-slate-200 bg-[#282a36] font-mono text-sm leading-6 text-[#f8f8f2] outline-none transition focus-within:border-emerald-600 focus-within:ring-4 focus-within:ring-emerald-600/10"
        value={script.code}
        onValueChange={(code) => update({ code })}
        highlight={(code) => Prism.highlight(code, Prism.languages.python, "python")}
        padding={16}
        textareaClassName="outline-none"
        preClassName="outline-none"
      />

      <div className="grid gap-3">
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex flex-wrap gap-3">
            <label className="inline-flex min-h-9 items-center gap-2 text-sm font-semibold text-slate-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600/20"
                checked={Boolean(script.trigger_on_enter)}
                onChange={(event) => update({ trigger_on_enter: event.target.checked })}
              />
              进入时执行
            </label>
            <label className="inline-flex min-h-9 items-center gap-2 text-sm font-semibold text-slate-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600/20"
                checked={scheduleEnabled}
                onChange={(event) => update({ schedule_rules: event.target.checked ? defaultScheduleRules() : [] })}
              />
              定时执行
            </label>
          </div>
          {scheduleEnabled ? (
            <div className="grid gap-2">
              {scheduleRules.map((rule) => (
                <div key={rule.id} className="grid gap-2 rounded-2xl border border-slate-200 bg-white p-2 md:grid-cols-[120px_1fr_112px_auto] md:items-center">
                  <select
                    className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
                    value={rule.kind}
                    onChange={(event) => updateScheduleRule(rule.id, { kind: event.target.value as NodeScriptScheduleRule["kind"], weekday: event.target.value === "weekly" ? (rule.weekday ?? 1) : undefined })}
                  >
                    <option value="daily">每天</option>
                    <option value="weekly">每周</option>
                  </select>
                  {rule.kind === "weekly" ? (
                    <select
                      className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 outline-none focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
                      value={rule.weekday ?? 1}
                      onChange={(event) => updateScheduleRule(rule.id, { weekday: Number(event.target.value) })}
                    >
                      {WEEKDAY_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  ) : (
                    <div className="hidden md:block" />
                  )}
                  <input
                    className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs font-semibold text-slate-700 outline-none focus:border-emerald-600 focus:bg-white focus:ring-4 focus:ring-emerald-600/10"
                    type="time"
                    value={normalizeTime(rule.time)}
                    onChange={(event) => updateScheduleRule(rule.id, { time: event.target.value })}
                  />
                  <button
                    className="rounded-full border border-rose-200 bg-white px-3 py-2 text-xs font-semibold text-rose-600 transition hover:bg-rose-50"
                    onClick={() => removeScheduleRule(rule.id)}
                    type="button"
                  >
                    删除
                  </button>
                </div>
              ))}
              <div className="flex flex-wrap gap-2">
                <button
                  className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
                  onClick={() => addScheduleRule("daily")}
                  type="button"
                >
                  添加每天时间
                </button>
                <button
                  className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
                  onClick={() => addScheduleRule("weekly")}
                  type="button"
                >
                  添加每周时间
                </button>
              </div>
            </div>
          ) : null}
        </div>
        {result ? (
          <pre className="max-h-36 overflow-auto rounded-2xl border border-slate-200 bg-slate-900 p-3 text-[11px] leading-5 text-emerald-50 whitespace-pre-wrap">
            {formatScriptResult(result)}
          </pre>
        ) : null}
      </div>
    </div>
  );
}

function ScriptEnvironmentHelp() {
  return (
    <span className="group relative inline-flex pb-3 -mb-3">
      <button
        className="grid h-5 w-5 place-items-center rounded-full border border-slate-200 bg-white text-[11px] font-bold text-slate-500 transition hover:border-slate-300 hover:text-slate-900 focus:outline-none focus:ring-4 focus:ring-emerald-600/10"
        type="button"
        aria-label="查看脚本运行环境"
      >
        ?
      </button>
      <span className="absolute left-1/2 top-[calc(100%+2px)] z-20 hidden w-[min(520px,calc(100vw-64px))] -translate-x-1/2 select-text rounded-2xl border border-slate-200 bg-white p-4 text-left text-xs font-normal leading-5 text-slate-600 shadow-[0_18px_50px_rgba(15,23,42,0.16)] group-hover:block group-focus-within:block">
        <strong className="mb-2 block text-sm font-semibold text-slate-900">脚本运行环境</strong>
        <span className="block font-semibold text-slate-700">可直接使用的函数</span>
        <code className="mb-2 block whitespace-pre-wrap rounded-xl bg-slate-50 p-2 font-mono text-[11px] text-slate-700">
          open_app(app, args=None, once=True, cwd=None){"\n"}
          list_node_files(){"\n"}
          get_node_file(file_id=None, name=None){"\n"}
          log(value)
        </code>
        <span className="block font-semibold text-slate-700">可直接使用的变量</span>
        <code className="mb-2 block whitespace-pre-wrap rounded-xl bg-slate-50 p-2 font-mono text-[11px] text-slate-700">
          NODE_ID{"\n"}
          SCRIPT_ARGS{"\n"}
          NODE_DATABASES{"\n"}
          NODE_FILES{"\n"}
          TRIGGER
        </code>
        <span className="block font-semibold text-slate-700">环境变量</span>
        <code className="block whitespace-pre-wrap rounded-xl bg-slate-50 p-2 font-mono text-[11px] text-slate-700">
          ME_AGENT_NODE_ID{"\n"}
          ME_AGENT_SCRIPT_ARGS{"\n"}
          ME_AGENT_NODE_DATABASES{"\n"}
          ME_AGENT_NODE_FILES{"\n"}
          ME_AGENT_SCRIPT_TRIGGER{"\n"}
          ME_AGENT_SCRIPTS_DIR
        </code>
        <span className="mt-2 block text-slate-500">脚本在项目根目录的 scripts/ 下运行；执行历史和代码快照写入 log/node-script-*.json。</span>
      </span>
    </span>
  );
}

const WEEKDAY_OPTIONS = [
  { value: 1, label: "星期一" },
  { value: 2, label: "星期二" },
  { value: 3, label: "星期三" },
  { value: 4, label: "星期四" },
  { value: 5, label: "星期五" },
  { value: 6, label: "星期六" },
  { value: 0, label: "星期日" }
];

function defaultScheduleRules(): NodeScriptScheduleRule[] {
  return [{ id: newScheduleRuleId(), kind: "daily", time: "09:00" }];
}

function newScheduleRuleId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `schedule_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `schedule_${Date.now().toString(36)}`;
}

function normalizeTime(value: string | undefined): string {
  return /^\d{2}:\d{2}$/.test(value ?? "") ? value as string : "09:00";
}

function formatScriptResult(result: NodeScriptRunResult): string {
  const header = `status=${result.status} returncode=${result.returncode ?? "-"} trigger=${result.trigger ?? "manual_run"}`;
  const pid = result.pid ? `\npid=${result.pid}` : "";
  const logPath = result.log_path ? `\nlog=${result.log_path}` : "";
  const scriptPath = result.script_path ? `\nscript=${result.script_path}` : "";
  const stdout = result.stdout ? `\nstdout:\n${result.stdout}` : "";
  const stderr = result.stderr ? `\nstderr:\n${result.stderr}` : "";
  return `${header}${pid}${logPath}${scriptPath}${stdout}${stderr}`;
}
