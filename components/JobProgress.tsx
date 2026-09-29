import { JobStatus } from "@/lib/api";

const STEPS = ["Pending", "Scanning", "Processing", "Matching", "Validating", "Exporting", "Completed"];

export default function JobProgress({ job }: { job: JobStatus }) {
  const stepIndex = STEPS.indexOf(job.status);
  const pct =
    job.status === "Processing" && job.progress_total > 0
      ? Math.round((job.progress_current / job.progress_total) * 100)
      : Math.round(((stepIndex + 1) / STEPS.length) * 100);

  const isFailed = job.status === "Failed";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-slate-800">Job Status</h3>
        <span
          className={`text-xs font-medium px-2 py-1 rounded-full ${
            isFailed ? "bg-red-100 text-red-700" : job.status === "Completed" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"
          }`}
        >
          {job.status}
        </span>
      </div>

      {isFailed ? (
        <p className="text-sm text-red-600">{job.error_details}</p>
      ) : (
        <>
          <div className="w-full bg-slate-100 rounded-full h-2.5 mb-2">
            <div className="bg-blue-600 h-2.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
          </div>
          <p className="text-xs text-slate-500">
            {job.status === "Processing"
              ? `Processing files: ${job.progress_current} / ${job.progress_total}`
              : `${pct}% complete`}
          </p>
        </>
      )}

      {job.mapping_unresolved && job.mapping_unresolved.length > 0 && (
        <p className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">
          Could not confidently map: {job.mapping_unresolved.join(", ")}. Resubmit with field_overrides.
        </p>
      )}
    </div>
  );
}
