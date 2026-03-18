"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

const fetcher = (url: string) => api.get(url);

export default function HealthPage() {
  const { data: stats, error } = useSWR("/admin/health/stats", fetcher, { refreshInterval: 30000 });
  const { data: gaps }         = useSWR("/admin/health/coverage-gaps", fetcher, { refreshInterval: 30000 });
  const { data: syncData }     = useSWR("/admin/health/last-sync", fetcher, { refreshInterval: 30000 });
  const { data: jobs }         = useSWR("/admin/sync/jobs?limit=5", fetcher, { refreshInterval: 10000 });

  return (
    <div className="max-w-5xl space-y-6">
      <h1 className="text-xl font-semibold">Graph Health</h1>

      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Neo4j Nodes",      value: stats?.neo4j_nodes },
          { label: "Relationships",    value: stats?.neo4j_relationships },
          { label: "Vector Chunks",    value: stats?.vector_chunks },
          { label: "Embedding Cover.", value: stats?.embedding_coverage_pct != null ? `${stats.embedding_coverage_pct}%` : "—" },
        ].map(m => (
          <div key={m.label} className="bg-[#1a1d27] border border-[#2e3348] rounded-xl p-4">
            <div className="text-[11px] text-[#7b82a0] mb-1">{m.label}</div>
            <div className="text-2xl font-bold">{m.value ?? "—"}</div>
          </div>
        ))}
      </div>

      {/* Coverage gaps */}
      <section className="bg-[#1a1d27] border border-[#2e3348] rounded-xl p-4">
        <h2 className="font-medium mb-3 text-sm">Coverage Gaps <span className="text-[#7b82a0]">(docs missing embeddings)</span></h2>
        {gaps?.gaps?.length === 0 && <p className="text-sm text-green-400">No gaps — all documents embedded.</p>}
        {gaps?.gaps?.map((d: any) => (
          <div key={d.id} className="flex items-center justify-between py-2 border-b border-[#2e3348] last:border-0 text-sm">
            <span>{d.filename}</span>
            <StatusBadge status={d.status} />
          </div>
        ))}
      </section>

      {/* Last sync */}
      <section className="bg-[#1a1d27] border border-[#2e3348] rounded-xl p-4">
        <h2 className="font-medium mb-3 text-sm">Last Sync per Document</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[#7b82a0] text-xs border-b border-[#2e3348]">
              <th className="pb-2 text-left">Filename</th>
              <th className="pb-2 text-left">Last Synced</th>
              <th className="pb-2 text-right">Nodes</th>
              <th className="pb-2 text-right">Chunks</th>
            </tr>
          </thead>
          <tbody>
            {syncData?.documents?.map((d: any) => (
              <tr key={d.id} className="border-b border-[#2e3348] last:border-0">
                <td className="py-2">{d.filename}</td>
                <td className="py-2 text-[#7b82a0]">{d.last_synced_at ? new Date(d.last_synced_at).toLocaleString() : "never"}</td>
                <td className="py-2 text-right">{d.node_count ?? 0}</td>
                <td className="py-2 text-right">{d.chunk_count ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Failed jobs */}
      <section className="bg-[#1a1d27] border border-[#2e3348] rounded-xl p-4">
        <h2 className="font-medium mb-3 text-sm">Recent Jobs</h2>
        {jobs?.jobs?.map((j: any) => (
          <div key={j.id} className="flex items-center justify-between py-2 border-b border-[#2e3348] last:border-0 text-sm">
            <span>{j.job_type}</span>
            <span className="text-[#7b82a0] text-xs">{j.duration_seconds ? `${j.duration_seconds}s` : "running"}</span>
            <StatusBadge status={j.status} />
          </div>
        ))}
      </section>
    </div>
  );
}
