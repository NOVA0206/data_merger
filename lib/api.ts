const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.API_URL || "";

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("session_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export interface JobStatus {
  id: string;
  status: string;
  progress_current: number;
  progress_total: number;
  source_type: string;
  error_details: string | null;
  created_at: string | null;
  completed_at: string | null;
  mapping_resolved: Record<string, string> | null;
  mapping_unresolved: string[] | null;
  mapping_ambiguous: Record<string, string[]> | null;
  summary: Record<string, number> | null;
}

export interface MatchRecordDTO {
  file_name: string;
  extracted_company_name: string;
  matched_company: string | null;
  status: string;
  method: string;
  confidence: number;
  source_file_id: string;
  notes: string;
}

export interface ValidationIssueDTO {
  issue_type: string;
  company_or_sheet_name: string;
  matched_company: string;
  problem: string;
  recommended_action: string;
  source_file: string;
  status: string;
}

export interface JobPreview {
  master_companies: string[];
  company_files: { source_id: string; file_name: string; extracted_company_name: string; read_error: string | null }[];
  match_records: MatchRecordDTO[];
  validation_issues: ValidationIssueDTO[];
  summary: Record<string, number> | null;
}

export const api = {
  googleLogin: () => request<{ url: string }>("/api/auth/google/login"),
  me: () => request<{ email: string }>("/api/me"),
  createJob: (payload: {
    source_type: "local" | "drive";
    local_path?: string;
    drive_folder_id?: string;
    field_overrides?: Record<string, string>;
  }) => request<{ job_id: string }>("/api/jobs", { method: "POST", body: JSON.stringify(payload) }),
  advanceJob: (jobId: string) => request<JobStatus>(`/api/jobs/${jobId}/advance`, { method: "POST" }),
  getJob: (jobId: string) => request<JobStatus>(`/api/jobs/${jobId}`),
  previewJob: (jobId: string) => request<JobPreview>(`/api/jobs/${jobId}/preview`),
  manualMatch: (jobId: string, sourceId: string, masterRowIndex: number) =>
    request<{ status: string }>(`/api/jobs/${jobId}/manual-match`, {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId, master_row_index: masterRowIndex }),
    }),
  downloadUrl: (jobId: string) => `${API_BASE}/api/jobs/${jobId}/download`,
  exportToSheets: (jobId: string) =>
    request<{ spreadsheet_url: string }>(`/api/jobs/${jobId}/export-to-sheets`, { method: "POST" }),
};

export const TERMINAL_STATUSES = new Set(["Completed", "Failed"]);
