"use client";

import { useEffect, useRef, useState } from "react";
import { api, JobPreview, JobStatus, TERMINAL_STATUSES } from "@/lib/api";
import JobProgress from "@/components/JobProgress";
import SummaryCards from "@/components/SummaryCards";
import MatchTable from "@/components/MatchTable";

const DEFAULT_COLUMNS = [
  "Company Name",
  "Director Name",
  "Director Email",
  "Director Contact Numbers",
  "Net Profit",
  "Revenue",
  "EBITDA",
  "City",
  "Company Products",
];

export default function Home() {
  const [sourceType, setSourceType] = useState<"local" | "drive">("local");
  const [localPath, setLocalPath] = useState("");
  const [driveFolderId, setDriveFolderId] = useState("");
  const [signedInEmail, setSignedInEmail] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [preview, setPreview] = useState<JobPreview | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const token = typeof window !== "undefined" ? window.localStorage.getItem("session_token") : null;
    if (token) {
      api.me().then((r) => setSignedInEmail(r.email)).catch(() => {
        window.localStorage.removeItem("session_token");
      });
    }
  }, []);

  useEffect(() => {
    if (!job || TERMINAL_STATUSES.has(job.status)) {
      if (pollRef.current) clearInterval(pollRef.current);
      if (job && job.status === "Completed") {
        api.previewJob(job.id).then(setPreview).catch(() => {});
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const updated = await api.advanceJob(job.id);
        setJob(updated);
        if (!TERMINAL_STATUSES.has(updated.status)) {
          const p = await api.previewJob(job.id).catch(() => null);
          if (p) setPreview(p);
        }
      } catch (e) {
        setErrorMsg((e as Error).message);
      }
    }, 1500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [job?.id, job?.status]);

  async function handleGoogleSignIn() {
    setErrorMsg(null);
    setSigningIn(true);
    try {
      const { url } = await api.googleLogin();
      window.location.href = url;
    } catch (e) {
      setErrorMsg(
        `Could not start Google sign-in: ${(e as Error).message}. ` +
          "If this is a fresh setup, confirm the backend's Google OAuth environment variables are configured, then try again."
      );
      setSigningIn(false);
    }
  }

  async function handleStart() {
    setErrorMsg(null);
    setStarting(true);
    try {
      const payload =
        sourceType === "local"
          ? { source_type: "local" as const, local_path: localPath }
          : { source_type: "drive" as const, drive_folder_id: driveFolderId };
      const { job_id } = await api.createJob(payload);
      const status = await api.advanceJob(job_id);
      setJob(status);
    } catch (e) {
      setErrorMsg((e as Error).message);
    } finally {
      setStarting(false);
    }
  }

  async function handleResolve(sourceFileId: string) {
    const rowIndexStr = window.prompt(
      "Enter the master-sheet row index to assign this file to (see Matching Log for candidates):"
    );
    if (rowIndexStr === null || !job) return;
    const rowIndex = parseInt(rowIndexStr, 10);
    if (Number.isNaN(rowIndex)) return;
    await api.manualMatch(job.id, sourceFileId, rowIndex);
    const status = await api.advanceJob(job.id);
    setJob(status);
  }

  async function handleExportToSheets() {
    if (!job) return;
    try {
      const { spreadsheet_url } = await api.exportToSheets(job.id);
      window.open(spreadsheet_url, "_blank");
    } catch (e) {
      setErrorMsg((e as Error).message);
    }
  }

  return (
    <main className="max-w-5xl mx-auto px-4 py-10 space-y-8">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Company Data Consolidation</h1>
        <p className="text-slate-500 mt-1">
          Merge master financial data with director/contact data into one verified database.
        </p>
      </header>

      {errorMsg && (
        <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm p-3">{errorMsg}</div>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h2 className="font-semibold text-slate-800">1. Choose data source</h2>
        <div className="flex gap-3">
          <button
            onClick={() => setSourceType("local")}
            className={`px-4 py-2 rounded-lg text-sm font-medium border ${sourceType === "local" ? "bg-blue-600 text-white border-blue-600" : "border-slate-300 text-slate-700"}`}
          >
            Local Folder
          </button>
          <button
            onClick={() => setSourceType("drive")}
            className={`px-4 py-2 rounded-lg text-sm font-medium border ${sourceType === "drive" ? "bg-blue-600 text-white border-blue-600" : "border-slate-300 text-slate-700"}`}
          >
            Google Drive
          </button>
        </div>

        {sourceType === "local" ? (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Parent folder path (server-accessible)
            </label>
            <input
              value={localPath}
              onChange={(e) => setLocalPath(e.target.value)}
              placeholder={String.raw`D:\Data Merging\Pune - Auto Ancillary (100)`}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        ) : (
          <div className="space-y-3">
            {!signedInEmail ? (
              <button
                onClick={handleGoogleSignIn}
                disabled={signingIn}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-slate-900 text-white disabled:opacity-50"
              >
                {signingIn ? "Connecting…" : "Connect Google Drive"}
              </button>
            ) : (
              <p className="text-sm text-green-700">Signed in as {signedInEmail}</p>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Parent folder ID</label>
              <input
                value={driveFolderId}
                onChange={(e) => setDriveFolderId(e.target.value)}
                placeholder="1AbCDefGhIjKLmNoPQRstuVWxyZ"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
        )}

        <div>
          <h3 className="text-sm font-medium text-slate-700 mb-1">Output columns (default)</h3>
          <div className="flex flex-wrap gap-2">
            {DEFAULT_COLUMNS.map((c) => (
              <span key={c} className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded-full">
                {c}
              </span>
            ))}
          </div>
        </div>

        <button
          onClick={handleStart}
          disabled={starting || (sourceType === "local" ? !localPath : !driveFolderId)}
          className="px-5 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:opacity-50"
        >
          {starting ? "Starting…" : "Start Data Consolidation"}
        </button>
      </section>

      {job && (
        <section className="space-y-4">
          <JobProgress job={job} />
          {job.summary && <SummaryCards summary={job.summary} />}
          {preview && preview.match_records.length > 0 && (
            <MatchTable matches={preview.match_records} onResolve={handleResolve} />
          )}
          {job.status === "Completed" && (
            <div className="flex gap-3">
              <a
                href={api.downloadUrl(job.id)}
                className="px-5 py-2.5 rounded-lg bg-green-600 text-white text-sm font-medium"
              >
                Download Consolidated Excel
              </a>
              {signedInEmail && (
                <button
                  onClick={handleExportToSheets}
                  className="px-5 py-2.5 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium"
                >
                  Save as Google Spreadsheet
                </button>
              )}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
