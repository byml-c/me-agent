import { GraphPanel } from "@/components/GraphPanel";

export default function GraphPage() {
  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-5 overflow-hidden p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Graph View</h1>
          <div className="mt-2 text-sm text-slate-500">默认展示当前锚点附近两跳局部图。</div>
        </div>
      </div>
      <section className="min-h-0 overflow-hidden rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
        <GraphPanel />
      </section>
    </div>
  );
}
