"use client";

import { useParams } from "next/navigation";

export default function ScriptPage() {
  const params = useParams<{ scriptId: string }>();
  return (
    <div className="grid gap-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Script Panel</h1>
          <div className="mt-2 text-sm text-slate-500">MVP 默认禁用脚本执行，只记录被拦截的执行事件。</div>
        </div>
      </div>
      <section className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
        <h2 className="mb-2 text-sm font-semibold text-slate-900">{params.scriptId}</h2>
        <div className="text-sm text-slate-500">脚本沙盒 runtime 尚未启用。</div>
      </section>
    </div>
  );
}
