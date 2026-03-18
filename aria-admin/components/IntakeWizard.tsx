"use client";
import { useState, useEffect } from "react";
import { api, sseStream } from "@/lib/api";

const STAGES = ["Identify", "Obsidian Prep", "Ingest", "Index", "Verify & Test"];

const DOC_TYPES = [
  { value: "sr_letter",      label: "SR Letter",               pattern: "GUIDANCE_SR-XX-YY.pdf" },
  { value: "occ_bulletin",   label: "OCC Bulletin",            pattern: "OCC_BULLETIN-YYYY-NN.pdf" },
  { value: "fed_guidance",   label: "Federal Reserve Guidance", pattern: "FED_Topic-YYYY.pdf" },
  { value: "nccob_circular", label: "NCCOB Circular",          pattern: "NCCOB_CIRCULAR-YYYY-NN.pdf" },
];

interface Props { onClose: () => void; }

export default function IntakeWizard({ onClose }: Props) {
  const [stage, setStage]             = useState(1);
  const [docType, setDocType]         = useState("");
  const [file, setFile]               = useState<File | null>(null);
  const [supersedes, setSupersedes]   = useState(false);
  const [sessionId, setSessionId]     = useState<string | null>(null);
  const [documentId, setDocumentId]   = useState<string | null>(null);
  const [template, setTemplate]       = useState("");
  const [related, setRelated]         = useState<any[]>([]);
  const [gateChecked, setGateChecked] = useState(false);
  const [gateConfirmed, setGateConfirmed] = useState(false);
  const [logLines, setLogLines]       = useState<string[]>([]);
  const [jobId, setJobId]             = useState<string | null>(null);
  const [jobDone, setJobDone]         = useState(false);
  const [verifyResult, setVerifyResult] = useState<string | null>(null);
  const [testAnswer, setTestAnswer]   = useState<string | null>(null);
  const [testRunning, setTestRunning] = useState(false);
  const [ingestDone, setIngestDone]   = useState(false);

  const docTypeMeta = DOC_TYPES.find(d => d.value === docType);

  // ── Stage 1: Confirm → upload + start session ─────────────────────────
  async function completeStage1() {
    if (!file || !docType) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);

    const uploadRes = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/admin/documents/upload`,
      {
        method: "POST",
        headers: { "X-Admin-Key": process.env.NEXT_PUBLIC_ADMIN_KEY ?? "" },
        body: formData,
      }
    );
    const uploadData = await uploadRes.json();
    const docId = uploadData.document?.id;
    setDocumentId(docId);

    const session = await api.post("/admin/intake/start", {
      document_id: docId,
      doc_type:    docType,
      triggered_by: "admin",
    });
    setSessionId(session.id);

    // Fetch template + related docs
    const tmpl = await api.post("/admin/intake/generate-template", {
      doc_type: docType,
      filename: file.name,
      date_issued: new Date().toISOString().slice(0, 10),
    });
    setTemplate(tmpl.template);

    const rel = await api.get(`/admin/documents/related?filename=${encodeURIComponent(file.name)}`);
    setRelated(rel.related ?? []);

    setStage(2);
  }

  // ── Stage 2: Obsidian gate ─────────────────────────────────────────────
  async function confirmObsidian() {
    if (!sessionId) return;
    await api.post(`/admin/intake/${sessionId}/confirm-obsidian`, {});
    setGateConfirmed(true);
    setStage(3);
    setTimeout(() => completeIngest(), 300);
  }

  // ── Stage 3: Ingest (auto) ─────────────────────────────────────────────
  async function completeIngest() {
    // Simulated sequential steps — actual work happened on upload
    await sleep(600); setIngestDone(true);
    await api.patch(`/admin/intake/${sessionId}/stage`, { stage: 4 });
    setStage(4);
    await startIndexing();
  }

  // ── Stage 4: Index ─────────────────────────────────────────────────────
  async function startIndexing() {
    const res = await api.post("/admin/sync/trigger", {
      job_type: "graphrag_incremental",
      triggered_by: "admin",
    });
    setJobId(res.job_id);
    setLogLines(["Starting GraphRAG incremental index..."]);

    const stop = sseStream(`/admin/sync/jobs/${res.job_id}/log`, (line) => {
      setLogLines(prev => [...prev, line]);
      if (line.includes("JOB COMPLETED") || line.includes("JOB FAILED")) {
        stop();
        setJobDone(true);
        checkVerification(line.includes("JOB COMPLETED"));
      }
    });
  }

  async function checkVerification(success: boolean) {
    if (!success) { setVerifyResult("failed"); return; }
    // Trigger embed after indexing
    await api.post("/admin/sync/trigger", { job_type: "embed", triggered_by: "admin" });
    setVerifyResult("passed");
    await api.patch(`/admin/intake/${sessionId}/stage`, { stage: 5 });
    setStage(5);
  }

  // ── Stage 5: Test ──────────────────────────────────────────────────────
  function autoTestQuery() {
    const name = file?.name?.replace(".pdf", "").replace(/_/g, " ") ?? "this regulation";
    const q: Record<string, string> = {
      sr_letter:      `What are the requirements under ${name}?`,
      occ_bulletin:   `What does ${name} require banks to implement?`,
      fed_guidance:   `What obligations does ${name} create?`,
      nccob_circular: `What does ${name} require for NC state-chartered banks?`,
    };
    return q[docType] ?? `What does ${name} require?`;
  }

  async function runTest() {
    setTestRunning(true);
    const res = await api.post("/admin/test/run", { question: autoTestQuery() });
    setTestAnswer(res.answer);
    setTestRunning(false);
  }

  async function completeIntake() {
    if (!sessionId) return;
    await api.post(`/admin/intake/${sessionId}/complete`, {});
    onClose();
  }

  async function flagIncorrect() {
    if (!testAnswer) return;
    await api.post("/admin/corrections", {
      question: autoTestQuery(),
      wrong_answer: testAnswer,
      flagged_by: "admin",
    });
    await completeIntake();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="bg-[#1a1d27] border border-[#2e3348] rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2e3348]">
          <h2 className="font-semibold text-lg">Regulation Intake Wizard</h2>
          <button onClick={onClose} className="text-[#7b82a0] hover:text-white text-xl">×</button>
        </div>

        {/* Progress bar */}
        <div className="px-6 py-3 border-b border-[#2e3348]">
          <div className="flex gap-1">
            {STAGES.map((s, i) => {
              const n = i + 1;
              const done = stage > n;
              const active = stage === n;
              return (
                <div key={s} className="flex-1 text-center">
                  <div className={`h-1.5 rounded-full mb-1.5
                    ${done ? "bg-green-500" : active ? "bg-indigo-500" : "bg-[#2e3348]"}`} />
                  <span className={`text-[10px] ${active ? "text-indigo-300" : done ? "text-green-400" : "text-[#7b82a0]"}`}>
                    {s}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="px-6 py-5">

          {/* ── STAGE 1: IDENTIFY ─────────────────────────────────────────── */}
          {stage === 1 && (
            <div className="space-y-4">
              <h3 className="font-medium">Stage 1: Identify Regulation</h3>
              <div>
                <label className="text-xs text-[#7b82a0] mb-1 block">Document Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {DOC_TYPES.map(d => (
                    <button key={d.value} onClick={() => setDocType(d.value)}
                      className={`p-3 rounded-lg border text-left text-sm transition-colors
                        ${docType === d.value
                          ? "border-indigo-500 bg-indigo-600/10 text-indigo-300"
                          : "border-[#2e3348] hover:border-[#7b82a0] text-[#e8eaf2]"}`}>
                      {d.label}
                      <div className="text-[10px] text-[#7b82a0] mt-0.5 font-mono">{d.pattern}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs text-[#7b82a0] mb-1 block">Upload PDF</label>
                <div className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors
                  ${file ? "border-green-500/50 bg-green-900/10" : "border-[#2e3348] hover:border-indigo-500"}`}
                  onClick={() => document.getElementById("pdf-input")?.click()}>
                  <input id="pdf-input" type="file" accept=".pdf" className="hidden"
                    onChange={e => setFile(e.target.files?.[0] ?? null)} />
                  {file
                    ? <p className="text-green-400 text-sm">✓ {file.name}</p>
                    : <p className="text-[#7b82a0] text-sm">Click to upload PDF</p>}
                </div>
              </div>

              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={supersedes} onChange={e => setSupersedes(e.target.checked)}
                  className="rounded" />
                This regulation supersedes an existing one
              </label>

              <button
                onClick={completeStage1}
                disabled={!file || !docType}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white py-2.5 rounded-lg text-sm font-medium"
              >
                Next: Prepare Obsidian Note →
              </button>
            </div>
          )}

          {/* ── STAGE 2: OBSIDIAN PREP ────────────────────────────────────── */}
          {stage === 2 && (
            <div className="space-y-4">
              <h3 className="font-medium">Stage 2: Obsidian Note Preparation</h3>

              {/* Amber warning */}
              <div className="bg-amber-900/20 border border-amber-600/40 rounded-lg p-3 text-sm text-amber-300">
                This step cannot be skipped. The Obsidian note connects this regulation to the
                knowledge graph. Without it, ARIA treats this as plain text — not a linked regulation.
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Left: template */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-xs text-[#7b82a0]">Frontmatter Template</p>
                    <button
                      onClick={() => navigator.clipboard.writeText(template)}
                      className="text-[10px] bg-[#22263a] hover:bg-[#2e3348] px-2 py-0.5 rounded text-[#7b82a0] hover:text-white">
                      Copy
                    </button>
                  </div>
                  <pre className="bg-[#0f1117] rounded-lg p-3 text-[10px] text-green-300 overflow-auto max-h-64 whitespace-pre-wrap">
                    {template}
                  </pre>
                </div>

                {/* Right: related docs */}
                <div>
                  <p className="text-xs text-[#7b82a0] mb-1.5">Related Regulations in Corpus</p>
                  {related.length === 0
                    ? <p className="text-xs text-[#7b82a0]">No related docs found in graph.</p>
                    : related.map((r: any, i: number) => (
                      <div key={i} className="flex items-center justify-between py-1.5 border-b border-[#2e3348] last:border-0">
                        <div>
                          <p className="text-xs">{r.target}</p>
                          <p className="text-[10px] text-[#7b82a0]">{r.relationship_type}</p>
                        </div>
                        <button
                          onClick={() => navigator.clipboard.writeText(`[[${r.target}]]`)}
                          className="text-[10px] bg-[#22263a] px-1.5 py-0.5 rounded text-[#7b82a0] hover:text-white">
                          Copy [[link]]
                        </button>
                      </div>
                    ))
                  }

                  <a
                    href={`https://github.com/${process.env.NEXT_PUBLIC_OBSIDIAN_GITHUB_REPO ?? ""}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 block text-center text-xs bg-amber-900/20 border border-amber-600/40 text-amber-300 rounded-lg py-2 hover:bg-amber-900/30"
                  >
                    View Vault on GitHub →
                  </a>
                </div>
              </div>

              {/* Hard gate */}
              <label className="flex items-start gap-3 cursor-pointer bg-[#22263a] rounded-lg p-3">
                <input type="checkbox" checked={gateChecked}
                  onChange={e => setGateChecked(e.target.checked)}
                  className="mt-0.5 rounded" />
                <span className="text-sm">
                  I have created the Obsidian note, filled in all frontmatter fields, added [[wikilinks]] to related regulations, and the Obsidian Git plugin has pushed the note to GitHub.
                </span>
              </label>

              <button
                onClick={confirmObsidian}
                disabled={!gateChecked}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed text-white py-2.5 rounded-lg text-sm font-medium"
              >
                Next: Ingest →
              </button>
            </div>
          )}

          {/* ── STAGE 3: INGEST ───────────────────────────────────────────── */}
          {stage === 3 && (
            <div className="space-y-3">
              <h3 className="font-medium">Stage 3: Ingest</h3>
              <IngestStep label="PDF staged to ./input/"              done={true} />
              <IngestStep label="Obsidian note path registered"       done={true} />
              <IngestStep label="intake_sessions record updated"      done={ingestDone} />
              {!ingestDone && <p className="text-sm text-[#7b82a0]">Preparing…</p>}
            </div>
          )}

          {/* ── STAGE 4: INDEX ────────────────────────────────────────────── */}
          {stage === 4 && (
            <div className="space-y-4">
              <h3 className="font-medium">Stage 4: Index</h3>
              <div className="bg-[#0f1117] rounded-lg p-3 h-48 overflow-y-auto font-mono text-xs text-green-400 space-y-0.5">
                {logLines.map((l, i) => <div key={i}>{l}</div>)}
                {!jobDone && <div className="animate-pulse">▋</div>}
              </div>
              {jobDone && verifyResult === "passed" && (
                <div className="bg-green-900/20 border border-green-600/40 rounded-lg p-3 text-sm text-green-300">
                  ✓ Indexing complete. Embedding triggered. Proceeding to verification…
                </div>
              )}
              {jobDone && verifyResult === "failed" && (
                <div className="bg-red-900/20 border border-red-600/40 rounded-lg p-3 text-sm text-red-300">
                  ✗ Indexing failed. Check Sync tab for details.
                </div>
              )}
            </div>
          )}

          {/* ── STAGE 5: VERIFY & TEST ────────────────────────────────────── */}
          {stage === 5 && (
            <div className="space-y-4">
              <h3 className="font-medium">Stage 5: Verify & Test</h3>
              <div className="bg-[#22263a] rounded-lg p-3 text-sm">
                <p className="text-xs text-[#7b82a0] mb-1">Auto-generated test query:</p>
                <p>{autoTestQuery()}</p>
              </div>
              <button
                onClick={runTest}
                disabled={testRunning}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white text-sm px-4 py-2 rounded-lg"
              >
                {testRunning ? "Running…" : "Run Test Query"}
              </button>
              {testAnswer && (
                <div className="space-y-3">
                  <div className="bg-[#0f1117] rounded-lg p-3 text-sm whitespace-pre-wrap max-h-48 overflow-y-auto">
                    {testAnswer}
                  </div>
                  <div className="flex gap-3">
                    <button onClick={completeIntake}
                      className="flex-1 bg-green-700 hover:bg-green-600 text-white text-sm py-2.5 rounded-lg font-medium">
                      ✓ ARIA answered correctly — Complete Intake
                    </button>
                    <button onClick={flagIncorrect}
                      className="flex-1 bg-red-900/40 hover:bg-red-900/60 border border-red-600/40 text-red-300 text-sm py-2.5 rounded-lg font-medium">
                      ✗ Flag as Incorrect
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

function IngestStep({ label, done }: { label: string; done: boolean }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={done ? "text-green-400" : "text-[#7b82a0] animate-pulse"}>
        {done ? "✓" : "○"}
      </span>
      <span className={done ? "text-[#e8eaf2]" : "text-[#7b82a0]"}>{label}</span>
    </div>
  );
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)); }
