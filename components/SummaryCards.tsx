export default function SummaryCards({ summary }: { summary: Record<string, number> }) {
  const entries = Object.entries(summary);
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-2xl font-semibold text-slate-800">{value}</p>
          <p className="text-xs text-slate-500 mt-1 capitalize">{key.replaceAll("_", " ")}</p>
        </div>
      ))}
    </div>
  );
}
