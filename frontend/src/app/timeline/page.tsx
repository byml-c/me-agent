"use client";

import { useEffect, useState } from "react";
import { api } from "@/api/client";
import type { EventLogItem } from "@/types";

export default function TimelinePage() {
  const [items, setItems] = useState<EventLogItem[]>([]);

  useEffect(() => {
    api.events.list().then(setItems).catch(console.error);
  }, []);

  return (
    <div className="grid gap-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Timeline</h1>
          <div className="mt-2 text-sm text-slate-500">append-only event log，用于审计图谱演化。</div>
        </div>
      </div>
      <section className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
        <div className="grid gap-3">
          {items.map((event) => (
            <div key={event.id} className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4">
              <div>
                <strong className="text-slate-900">{event.type}</strong>
                <div className="mt-1 text-sm text-slate-500">{event.created_at}</div>
                <pre className="mt-2 overflow-auto rounded-xl bg-slate-50 p-3 text-xs leading-6 text-slate-500">
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              </div>
              <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-3 text-xs font-medium text-slate-500">
                {event.actor}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
