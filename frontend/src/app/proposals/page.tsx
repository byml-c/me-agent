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
    <div className="grid gap-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Proposal Inbox</h1>
          <div className="mt-2 text-sm text-slate-500">高风险图更新必须在这里确认或拒绝。</div>
        </div>
      </div>
      <section className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
        <div className="grid gap-3">
          {items.map((proposal) => (
            <div key={proposal.id} className="flex items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4">
              <div>
                <strong className="text-slate-900">{proposal.operation}</strong>
                <div className="mt-1 text-sm text-slate-500">{proposal.reason}</div>
                <pre className="mt-2 overflow-auto rounded-xl bg-slate-50 p-3 text-xs leading-6 text-slate-500">
                  {JSON.stringify(proposal.payload, null, 2)}
                </pre>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex h-6 items-center rounded-full bg-slate-100 px-3 text-xs font-medium text-slate-500">
                  {proposal.status}
                </span>
                {proposal.status === "pending" ? (
                  <>
                    <button
                      className="inline-flex h-10 items-center gap-2 rounded-full bg-emerald-700 px-4 text-sm font-medium text-white transition hover:bg-emerald-800"
                      onClick={() => resolve(proposal.id, true)}
                    >
                      <Check size={16} />
                      接受
                    </button>
                    <button
                      className="inline-flex h-10 items-center gap-2 rounded-full border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                      onClick={() => resolve(proposal.id, false)}
                    >
                      <X size={16} />
                      拒绝
                    </button>
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
