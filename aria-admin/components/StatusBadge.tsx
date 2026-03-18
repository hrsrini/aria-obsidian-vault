const MAP: Record<string, string> = {
  pending:     "bg-gray-700 text-gray-300",
  indexed:     "bg-green-900/50 text-green-400",
  failed:      "bg-red-900/50 text-red-400",
  superseded:  "bg-amber-900/50 text-amber-400",
  running:     "bg-blue-900/50 text-blue-400",
  completed:   "bg-green-900/50 text-green-400",
  pass:        "bg-green-900/50 text-green-400",
  fail:        "bg-red-900/50 text-red-400",
  not_run:     "bg-gray-700 text-gray-300",
  flagged:     "bg-red-900/50 text-red-400",
  in_review:   "bg-amber-900/50 text-amber-400",
  re_testing:  "bg-blue-900/50 text-blue-400",
  resolved:    "bg-green-900/50 text-green-400",
  wont_fix:    "bg-gray-700 text-gray-300",
  in_progress: "bg-blue-900/50 text-blue-400",
  complete:    "bg-green-900/50 text-green-400",
  abandoned:   "bg-gray-700 text-gray-300",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = MAP[status] ?? "bg-gray-700 text-gray-300";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
