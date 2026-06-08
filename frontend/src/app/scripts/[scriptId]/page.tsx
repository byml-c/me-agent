"use client";

import { useParams } from "next/navigation";

export default function ScriptPage() {
  const params = useParams<{ scriptId: string }>();
  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Script Panel</h1>
          <div className="page-subtitle">MVP 默认禁用脚本执行，只记录被拦截的执行事件。</div>
        </div>
      </div>
      <section className="card">
        <h2>{params.scriptId}</h2>
        <div className="muted">脚本沙盒 runtime 尚未启用。</div>
      </section>
    </div>
  );
}
