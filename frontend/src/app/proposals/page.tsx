"use client";

import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { api } from "@/api/client";
import type { Proposal } from "@/types";

export default function ProposalsPage() {
  const [items, setItems] = useState<Proposal[]>([]);

  function refresh() {
    api.proposals.list().then(setItems).catch(console.error);
  }

  useEffect(refresh, []);

  async function resolve(id: string, accept: boolean) {
    if (accept) {
      await api.proposals.accept(id);
    } else {
      await api.proposals.reject(id);
    }
    refresh();
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Proposal Inbox</h1>
          <div className="page-subtitle">高风险图更新必须在这里确认或拒绝。</div>
        </div>
      </div>
      <section className="card">
        <div className="list">
          {items.map((proposal) => (
            <div key={proposal.id} className="row">
              <div>
                <strong>{proposal.operation}</strong>
                <div className="muted">{proposal.reason}</div>
                <pre className="muted">{JSON.stringify(proposal.payload, null, 2)}</pre>
              </div>
              <div className="row">
                <span className="pill">{proposal.status}</span>
                {proposal.status === "pending" ? (
                  <>
                    <button className="button primary" onClick={() => resolve(proposal.id, true)}><Check size={16} />接受</button>
                    <button className="button" onClick={() => resolve(proposal.id, false)}><X size={16} />拒绝</button>
                  </>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
