"use client";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";

const fetcher = (url: string) => api.get(url);

type Tab = "adhoc" | "library" | "regression";

export default function TestsPage() {
  const [tab, setTab] = useState<Tab>("adhoc");

  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-xl font-semibold">Test Console</h1>
      <div className="flex gap-2 border-b border-[#2e3348] pb-2">
        {(["adhoc", "library", "regression"] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm rounded-t font-medium transition-colors capitalize
              ${tab === t ? "text-indigo-300 border-b-2 border-indigo-500" : "text-[#7b82a0] hover:text-white"}`}>
            {t === "adhoc" ? "Ad-hoc" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === "adhoc"      && <AdHocTab />}
      {tab === "library"    && <LibraryTab />}
      {tab === "regression" && <RegressionTab />}
    </div>
  );
}

// ── Ad-hoc ────────────────────────────────────────────────────────────────

function AdHocTab() {
  const [question, setQuestion]   = useState("");
  const [role, setRole]           = useState("");
  const [bankSize, setBankSize]   = useState("");
  const [loading, setLoading]     = useState(false);
  const [result, setResult]       = useState<any>(null);
  const [showRaw, setShowRaw]     = useState(false);

  async function run() {
    if (!question.trim()) return;
    setLoading(true);
    try {
      const res = await api.post("/admin/test/run", {
        question, role_filter: role || null, bank_size_filter: bankSize || null
      });
      setResult(res);
    } finally {
      setLoading(false);
    }
  }

  async function flag() {
    if (!result) return;
    await api.post("/admin/corrections", {
      question,
      wrong_answer: result.answer,
      flagged_by: "admin",
    });
    alert("Flagged as incorrect. Find it in the Corrections tab.");
  }

  async function saveToLibrary() {
    const expected = prompt("Enter expected answer (or key phrase):");
    if (!expected) return;
    const category = prompt("Category (foundational/multi-hop/role/state-federal/edge):", "foundational");
    await api.post("/admin/test/library", {
      question, expected_answer: expected, category: category ?? "foundational", created_by: "admin"
    });
    alert("Saved to library.");
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <select value={role} onChange={e => setRole(e.target.value)}
          className="bg-[#1a1d27] border border-[#2e3348] rounded-lg px-3 py-2 text-sm text-[#e8eaf2]">
          <option value="">All Roles</option>
          <option>CRO</option><option>CISO</option><option>Board</option><option>CFO</option>
        </select>
        <select value={bankSize} onChange={e => setBankSize(e.target.value)}
          className="bg-[#1a1d27] border border-[#2e3348] rounded-lg px-3 py-2 text-sm text-[#e8eaf2]">
          <option value="">All Sizes</option>
          <option>$1Bn</option><option>$10Bn</option><option>$50Bn+</option>
        </select>
      </div>
      <div className="flex gap-2">
        <textarea
          value={question} onChange={e => setQuestion(e.target.value)}
          placeholder="Enter compliance question…"
          rows={2}
          className="flex-1 bg-[#1a1d27] border border-[#2e3348] rounded-lg px-3 py-2 text-sm resize-none text-[#e8eaf2] placeholder-[#7b82a0] focus:outline-none focus:border-indigo-500"
        />
        <button onClick={run} disabled={loading || !question.trim()}
          className="px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white rounded-lg text-sm font-medium">
          {loading ? "…" : "Run"}
        </button>
      </div>
      {result && (
        <div className="bg-[#1a1d27] border border-[#2e3348] rounded-xl p-4 space-y-3">
          <p className="text-sm whitespace-pre-wrap">{result.answer}</p>
          <div className="flex gap-2 pt-2 border-t border-[#2e3348]">
            <button onClick={() => setShowRaw(v => !v)} className="btn-sm">
              {showRaw ? "Hide" : "Show"} Raw Context
            </button>
            <button onClick={saveToLibrary} className="btn-sm text-green-400">Save to Library</button>
            <button onClick={flag}          className="btn-sm text-red-400">Flag as Incorrect</button>
          </div>
          {showRaw && (
            <pre className="text-xs bg-[#0f1117] p-3 rounded overflow-auto max-h-60 text-[#7b82a0]">
              {JSON.stringify(result.raw_context, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ── Library ───────────────────────────────────────────────────────────────

function LibraryTab() {
  const { data, mutate } = useSWR("/admin/test/library", fetcher);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [running, setRunning]   = useState(false);

  async function runAll() {
    setRunning(true);
    await api.post("/admin/test/run-library", {});
    await mutate();
    setRunning(false);
  }

  async function runOne(id: string, question: string) {
    const res = await api.post("/admin/test/run", { question });
    mutate();
    alert(res.answer?.slice(0, 300));
  }

  async function deleteCase(id: string) {
    if (!confirm("Delete this test case?")) return;
    await api.delete(`/admin/test/library/${id}`);
    mutate();
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-sm text-[#7b82a0]">{data?.test_cases?.length ?? 0} test cases</span>
        <button onClick={runAll} disabled={running}
          className="text-sm bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white px-4 py-1.5 rounded-lg">
          {running ? "Running…" : "Run All"}
        </button>
      </div>
      {data?.test_cases?.map((tc: any) => (
        <div key={tc.id} className="bg-[#1a1d27] border border-[#2e3348] rounded-xl overflow-hidden">
          <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#22263a]"
            onClick={() => setExpanded(expanded === tc.id ? null : tc.id)}>
            <StatusBadge status={tc.last_result} />
            <p className="flex-1 text-sm truncate">{tc.question}</p>
            <span className="text-[11px] text-[#7b82a0]">{tc.category}</span>
          </div>
          {expanded === tc.id && (
            <div className="px-4 pb-3 border-t border-[#2e3348] pt-3 space-y-2">
              <p className="text-xs text-[#7b82a0]">Expected:</p>
              <p className="text-sm bg-[#0f1117] p-2 rounded">{tc.expected_answer}</p>
              {tc.last_actual && <>
                <p className="text-xs text-[#7b82a0]">Last actual:</p>
                <p className="text-sm bg-[#0f1117] p-2 rounded text-[#7b82a0]">{tc.last_actual}</p>
              </>}
              <div className="flex gap-2">
                <button onClick={() => runOne(tc.id, tc.question)} className="btn-sm">Run</button>
                <button onClick={() => deleteCase(tc.id)} className="btn-sm text-red-400">Delete</button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Regression ────────────────────────────────────────────────────────────

function RegressionTab() {
  const { data } = useSWR("/admin/test/regression-history", fetcher, { refreshInterval: 30000 });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Pass Rate",  value: data ? `${data.pass_rate}%` : "—", color: "text-green-400" },
          { label: "Failing",    value: data?.fail_count ?? "—",           color: "text-red-400" },
          { label: "Not Run",    value: data?.not_run ?? "—",              color: "text-[#7b82a0]" },
        ].map(m => (
          <div key={m.label} className="bg-[#1a1d27] border border-[#2e3348] rounded-xl p-4 text-center">
            <div className={`text-2xl font-bold ${m.color}`}>{m.value}</div>
            <div className="text-[11px] text-[#7b82a0] mt-1">{m.label}</div>
          </div>
        ))}
      </div>
      <p className="text-sm text-[#7b82a0]">Regression runs automatically after every sync job completes.</p>
    </div>
  );
}
