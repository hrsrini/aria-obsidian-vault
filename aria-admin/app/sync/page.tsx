"use client";
import { useState, useEffect, useRef } from "react";
import useSWR from "swr";
import { api, sseStream } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

const fetcher = (url: string) => api.get(url);

const JOB_TYPES = [
  { type: "obsidian_sync",        label: "Obsidian Sync",       desc: "Sync vault notes → Neo4j" },
  { type: "graphrag_incremental", label: "GraphRAG Incremental", desc: "Index new docs only" },
  { type: "graphrag_full",        label: "GraphRAG Full",        desc: "Full re-index (slow)" },
  { type: "embed",                label: "Re-Embed Vault",       desc: "Re-run Voyage-3 embeddings" },
];

export default function SyncPage() {
  const [logLines, setLogLines]     = useState<string[]>([]);
  const [activeJob, setActiveJob]   = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);

  const { data: jobs, mutate } = useSWR("/admin/sync/jobs", fetcher, { refreshInterval: 5000 });

  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logLines, autoScroll]);

  async function trigger(jobType: string) {
    setConfirming(null);
    setLogLines([`Starting ${jobType}...`]);
    const res = await api.post("/admin/sync/trigger", { job_type: jobType, triggered_by: "admin" });
    setActiveJob(res.job_id);
    mutate();

    const stop = sseStream(`/admin/sync/jobs/${res.job_id}/log`, (line) => {
      setLogLines(prev => [...prev, line]);
      if (line.includes("JOB COMPLETED") || line.includes("JOB FAILED")) {
        stop();
        mutate();
      }
    });
  }

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-xl font-semibold">Sync Controls</h1>

      {/* Trigger buttons */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {JOB_TYPES.map(j => (
          <div key={j.type} className="bg-[#1a1d27] border border-[#2e3348] rounded-xl p-4">
            <div className="font-medium text-sm mb-1">{j.label}</div>
            <div className="text-[11px] text-[#7b82a0] mb-3">{j.desc}</div>
            {confirming === j.type ? (
              <div className="space-y-2">
                <p className="text-xs text-amber-400">Confirm trigger?</p>
                <div className="flex gap-2">
                  <button onClick={() => trigger(j.type)} className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white px-2 py-1 rounded">Yes</button>
                  <button onClick={() => setConfirming(null)} className="text-xs bg-[#22263a] text-[#7b82a0] px-2 py-1 rounded">No</button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setConfirming(j.type)}
                className="text-xs bg-[#22263a] hover:bg-indigo-600/20 border border-[#2e3348] hover:border-indigo-500 text-[#e8eaf2] px-3 py-1.5 rounded-lg w-full transition-colors"
              >
                Trigger
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Live log */}
      {logLines.length > 0 && (
        <div className="bg-[#1a1d27] border border-[#2e3348] rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-[#2e3348]">
            <span className="text-sm font-medium">Live Log {activeJob && <span className="text-[11px] text-[#7b82a0] ml-2">{activeJob.slice(0, 8)}</span>}</span>
            <button onClick={() => setAutoScroll(v => !v)} className="text-[11px] text-[#7b82a0] hover:text-white">
              {autoScroll ? "Pause scroll" : "Resume scroll"}
            </button>
          </div>
          <div ref={logRef} className="h-64 overflow-y-auto p-3 font-mono text-xs text-green-400 bg-[#0f1117] space-y-0.5">
            {logLines.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        </div>
      )}

      {/* Job history */}
      <section className="bg-[#1a1d27] border border-[#2e3348] rounded-xl p-4">
        <h2 className="font-medium text-sm mb-3">Job History</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[#7b82a0] text-xs border-b border-[#2e3348]">
              <th className="pb-2 text-left">Type</th>
              <th className="pb-2 text-left">By</th>
              <th className="pb-2 text-left">Started</th>
              <th className="pb-2 text-right">Duration</th>
              <th className="pb-2 text-right">Status</th>
            </tr>
          </thead>
          <tbody>
            {jobs?.jobs?.map((j: any) => (
              <tr key={j.id} className="border-b border-[#2e3348] last:border-0">
                <td className="py-2">{j.job_type}</td>
                <td className="py-2 text-[#7b82a0]">{j.triggered_by}</td>
                <td className="py-2 text-[#7b82a0]">{new Date(j.started_at).toLocaleString()}</td>
                <td className="py-2 text-right">{j.duration_seconds ? `${j.duration_seconds}s` : "—"}</td>
                <td className="py-2 text-right"><StatusBadge status={j.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
