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
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Timeline</h1>
          <div className="page-subtitle">append-only event log，用于审计图谱演化。</div>
        </div>
      </div>
      <section className="card">
        <div className="list">
          {items.map((event) => (
            <div key={event.id} className="row">
              <div>
                <strong>{event.type}</strong>
                <div className="muted">{event.created_at}</div>
                <pre className="muted">{JSON.stringify(event.payload, null, 2)}</pre>
              </div>
              <span className="pill">{event.actor}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
