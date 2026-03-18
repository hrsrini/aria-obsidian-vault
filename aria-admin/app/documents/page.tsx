"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import IntakeWizard from "@/components/IntakeWizard";

const fetcher = (url: string) => api.get(url);

const FILTERS = ["all", "pending", "indexed", "failed", "superseded"];

export default function DocumentsPage() {
  const [filter, setFilter]       = useState("all");
  const [showWizard, setShowWizard] = useState(false);

  const url = filter === "all" ? "/admin/documents" : `/admin/documents?status=${filter}`;
  const { data, mutate } = useSWR(url, fetcher, { refreshInterval: 15000 });

  async function markSuperseded(id: string) {
    const newId = prompt("Enter the document ID that supersedes this one:");
    if (!newId) return;
    await api.patch(`/admin/documents/${id}/supersede`, { superseded_by_id: newId });
    mutate();
  }

  async function reindex(id: string) {
    await api.post(`/admin/documents/${id}/reindex`, {});
    alert("Reindex job started. Check Sync tab for progress.");
  }

  return (
    <div className="max-w-6xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Document Corpus</h1>
        <button
          onClick={() => setShowWizard(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2 rounded-lg font-medium"
        >
          + New Regulation
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {FILTERS.map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors capitalize
              ${filter === f
                ? "bg-indigo-600 text-white"
                : "bg-[#1a1d27] text-[#7b82a0] hover:text-white border border-[#2e3348]"}`}>
            {f}
          </button>
        ))}
      </div>

      {/* Documents table */}
      <div className="bg-[#1a1d27] border border-[#2e3348] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[#7b82a0] text-xs border-b border-[#2e3348]">
              <th className="px-4 py-3 text-left">Filename</th>
              <th className="px-4 py-3 text-left">Source</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Stage</th>
              <th className="px-4 py-3 text-left">Last Synced</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data?.documents?.map((doc: any) => (
              <tr key={doc.id} className="border-b border-[#2e3348] last:border-0 hover:bg-[#22263a]/50">
                <td className="px-4 py-3 font-mono text-xs">{doc.filename}</td>
                <td className="px-4 py-3 text-[#7b82a0]">{doc.source_type}</td>
                <td className="px-4 py-3"><StatusBadge status={doc.status} /></td>
                <td className="px-4 py-3 text-[#7b82a0]">{doc.intake_stage ?? "—"}</td>
                <td className="px-4 py-3 text-[#7b82a0] text-xs">
                  {doc.last_synced_at ? new Date(doc.last_synced_at).toLocaleDateString() : "never"}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => reindex(doc.id)}
                      className="btn-sm">Reindex</button>
                    {doc.status !== "superseded" && (
                      <button onClick={() => markSuperseded(doc.id)}
                        className="btn-sm text-amber-400">Supersede</button>
                    )}
                    {doc.obsidian_path && (
                      <a
                        href={`https://github.com/${process.env.NEXT_PUBLIC_OBSIDIAN_GITHUB_REPO ?? ""}/blob/main/${encodeURIComponent(doc.obsidian_path)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-sm text-indigo-400"
                      >
                        View Note
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!data?.documents?.length && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[#7b82a0] text-sm">
                  No documents yet. Click &quot;+ New Regulation&quot; to add one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showWizard && (
        <IntakeWizard
          onClose={() => { setShowWizard(false); mutate(); }}
        />
      )}
    </div>
  );
}
