import { GraphPanel } from "@/components/GraphPanel";

export default function GraphPage() {
  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Graph View</h1>
          <div className="page-subtitle">默认展示当前锚点附近两跳局部图。</div>
        </div>
      </div>
      <section className="card">
        <GraphPanel />
      </section>
    </div>
  );
}
