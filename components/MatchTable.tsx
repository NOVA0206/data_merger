import { MatchRecordDTO } from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  "Exact Match": "bg-green-100 text-green-700",
  "Normalized Match": "bg-green-100 text-green-700",
  "Possible Match": "bg-amber-100 text-amber-700",
  "No Match": "bg-red-100 text-red-700",
  "Manual Review Required": "bg-red-100 text-red-700",
};

export default function MatchTable({
  matches,
  onResolve,
}: {
  matches: MatchRecordDTO[];
  onResolve?: (sourceFileId: string) => void;
}) {
  const needsReview = matches.filter((m) => m.status !== "Exact Match" && m.status !== "Normalized Match");
  const rows = needsReview.length > 0 ? needsReview : matches;

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100">
        <h3 className="font-semibold text-slate-800">
          {needsReview.length > 0 ? `Matches needing review (${needsReview.length})` : "All matches (exact/normalized)"}
        </h3>
      </div>
      <div className="overflow-x-auto max-h-96">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 sticky top-0">
            <tr>
              <th className="text-left px-4 py-2 font-medium">File</th>
              <th className="text-left px-4 py-2 font-medium">Extracted Name</th>
              <th className="text-left px-4 py-2 font-medium">Matched Company</th>
              <th className="text-left px-4 py-2 font-medium">Status</th>
              <th className="text-left px-4 py-2 font-medium">Confidence</th>
              {onResolve && <th className="text-left px-4 py-2 font-medium">Action</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.source_file_id} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-700 max-w-[220px] truncate" title={m.file_name}>
                  {m.file_name}
                </td>
                <td className="px-4 py-2 text-slate-700">{m.extracted_company_name}</td>
                <td className="px-4 py-2 text-slate-700">{m.matched_company || "—"}</td>
                <td className="px-4 py-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${STATUS_COLORS[m.status] || "bg-slate-100 text-slate-600"}`}>
                    {m.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-600">{(m.confidence * 100).toFixed(0)}%</td>
                {onResolve && (
                  <td className="px-4 py-2">
                    <button
                      onClick={() => onResolve(m.source_file_id)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Resolve manually
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
