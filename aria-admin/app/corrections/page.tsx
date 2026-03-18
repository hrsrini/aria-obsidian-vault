"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

const fetcher = (url: string) => api.get(url);

const STATUSES = ["all", "flagged", "in_review", "re_testing", "resolved", "wont_fix"];

export default function CorrectionsPage() {
  const [filter, setFilter]   = useState("flagged");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [retestResult, setRetestResult] = useState<Record<string, string>>({});

  const url = filter === "all" ? "/admin/corrections" : `/admin/corrections?status=${filter}`;
  const { data, mutate } = useSWR(url, fetcher, { refreshInterval: 15000 });

  async function updateStatus(id: string, status: string) {
    await api.patch(`/admin/corrections/${id}`, { status });
    mutate();
  }

  async function retest(id: string) {
    const res = await api.post(`/admin/corrections/${id}/retest`, {});
    setRetestResult(prev => ({ ...prev, [id]: res.new_answer }));
    mutate();
  }

  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-xl font-semibold">Corrections</h1>

      <div className="flex gap-2">
        {STATUSES.map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors
              ${filter === s ? "bg-indigo-600 text-white" : "bg-[#1a1d27] text-[#7b82a0] hover:text-white border border-[#2e3348]"}`}
          >
            {s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {data?.corrections?.map((c: any) => (
          <div key={c.id} className="bg-[#1a1d27] border border-[#2e3348] rounded-xl overflow-hidden">
            <div
              className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-[#22263a]"
              onClick={() => setExpanded(expanded === c.id ? null : c.id)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{c.question}</p>
                <p className="text-[11px] text-[#7b82a0]">by {c.flagged_by} · {new Date(c.created_at).toLocaleDateString()}</p>
              </div>
              <StatusBadge status={c.status} />
            </div>

            {expanded === c.id && (
              <div className="px-4 pb-4 border-t border-[#2e3348] space-y-3 pt-3">
                <div>
                  <p className="text-xs text-[#7b82a0] mb-1">Wrong answer</p>
                  <p className="text-sm bg-[#0f1117] rounded p-2 text-red-300 whitespace-pre-wrap">{c.wrong_answer?.slice(0, 500)}</p>
                </div>
                {c.correct_answer && (
                  <div>
                    <p className="text-xs text-[#7b82a0] mb-1">Correct answer</p>
                    <p className="text-sm bg-[#0f1117] rounded p-2 text-green-300 whitespace-pre-wrap">{c.correct_answer?.slice(0, 500)}</p>
                  </div>
                )}
                {retestResult[c.id] && (
                  <div>
                    <p className="text-xs text-[#7b82a0] mb-1">Retest result</p>
                    <p className="text-sm bg-[#0f1117] rounded p-2 text-blue-300 whitespace-pre-wrap">{retestResult[c.id].slice(0, 500)}</p>
                  </div>
                )}
                <div className="flex gap-2 flex-wrap">
                  <button onClick={() => updateStatus(c.id, "in_review")}   className="btn-sm">Mark In Review</button>
                  <button onClick={() => updateStatus(c.id, "resolved")}    className="btn-sm text-green-400">Resolve</button>
                  <button onClick={() => updateStatus(c.id, "wont_fix")}    className="btn-sm text-gray-400">Won&apos;t Fix</button>
                  <button onClick={() => retest(c.id)}                      className="btn-sm text-blue-400">Re-test</button>
                  {c.obsidian_note && (
                    <a href={c.obsidian_note} className="btn-sm text-amber-400">Open in Obsidian</a>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
        {!data?.corrections?.length && (
          <p className="text-sm text-[#7b82a0] py-8 text-center">No corrections with status: {filter}</p>
        )}
      </div>
    </div>
  );
}
