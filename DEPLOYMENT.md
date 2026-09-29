# Deployment Guide (Vercel: frontend + Python backend, one project)

## Prerequisites

- A Postgres database (Neon, Supabase, Railway, or Vercel Postgres all work).
- A Google Cloud project with Drive API + Sheets API enabled and an OAuth client
  (see README.md "Google Cloud OAuth setup").
- A GitHub repo containing this project, connected to Vercel.

## Step 1 — Google Cloud

Enable **Google Drive API** and **Google Sheets API**. Create an OAuth 2.0 Client ID
(Web application). Leave the redirect URI blank for now — you'll add the real one after
step 5 gives you the production domain, then come back and update it.

## Step 2 — Provision Postgres

Create the database, copy its connection string. SQLAlchemy will create all tables
automatically on first cold start (`init_db()` runs on FastAPI startup) — no manual
migration step is required, but `sql/schema.sql` is there if you prefer to run it by hand.

## Step 3 — Import the repo into Vercel

Vercel auto-detects this as a Next.js project and additionally picks up `api/index.py`
(with `api/requirements.txt` alongside it) as a Python serverless function — no custom
`vercel.json` builds config is needed beyond what's already committed (function timeout +
cron). Root Directory should be the repo root (where `package.json` and `api/` both live).

## Step 4 — Configure environment variables (Vercel Project Settings → Environment Variables)

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=https://<your-domain>/api/auth/google/callback
GOOGLE_TOKEN_ENCRYPTION_KEY=<output of Fernet.generate_key()>
FRONTEND_URL=https://<your-domain>
DATABASE_URL=postgresql://...
JOB_BATCH_SIZE=8
CRON_SECRET=<any random string>
NEXT_PUBLIC_API_URL=            # leave blank; same-origin /api/*
```

Deploy. Vercel gives you the production domain.

## Step 5 — Close the loop on Google OAuth

Go back to the OAuth client in Google Cloud and add the **exact** redirect URI:
`https://<your-domain>/api/auth/google/callback`. Update `GOOGLE_REDIRECT_URI` and
`FRONTEND_URL` in Vercel if the domain differs from what you guessed in Step 4, then
redeploy (env var changes require a redeploy to take effect).

## Step 6 — Test Google Drive connectivity

1. Open the deployed app, click "Connect Google Drive".
2. Approve the consent screen (scopes: Drive read-only, Drive file-create, Sheets,
   email).
3. You should land back on `/auth/callback`, which stores the session token and redirects
   to `/`, showing "Signed in as ...".
4. If this fails: check the redirect URI matches exactly (including https vs http and
   trailing slash), and check Vercel function logs for the `/api/auth/google/callback`
   invocation.

## Step 7 — Run a real consolidation job

1. Paste the parent Drive folder ID (the folder containing `Main Sheet/` and the company
   spreadsheets) into the Drive folder ID field.
2. Click "Start Data Consolidation". The frontend polls `/api/jobs/{id}/advance` every
   1.5s; each call performs one bounded chunk of work (a Scanning step, a batch of files,
   Matching, Validating, or Exporting), so no single request should exceed the configured
   `maxDuration` (60s in `vercel.json`; raise this — Vercel Pro allows up to 300s/800s — or
   lower `JOB_BATCH_SIZE` if a batch of files is slow to read).
3. Watch the status move through Scanning → Processing → Matching → Validating →
   Exporting → Completed. Review any "Possible Match" / "Manual Review Required" rows in
   the match table before trusting the output.
4. The Vercel Cron entry (`/api/cron/advance-jobs`, every minute) is a safety net: if the
   browser tab is closed mid-job, the cron will keep advancing any job untouched for 90+
   seconds. **Note:** per-minute cron schedules require a paid Vercel plan; on Hobby, cron
   runs at most once a day, so treat this purely as a resume mechanism, not the primary
   driver, for jobs left unattended on the free tier.

## Step 8 — Verify the output

Download the Excel file and/or click "Save as Google Spreadsheet". Confirm:
- `Final Consolidated Data` has exactly one row per master company.
- Director name/email/phone stay aligned per director.
- `Validation & Review` lists every ambiguous/unmatched/missing-field case with a clear
  problem + recommended action.
- `Matching Log` shows Match Status/Method/Confidence for every spreadsheet scanned.

## Step 9 — Error handling / auth checks

- Try starting a Drive job while signed out → should return 401, surfaced in the UI.
- Try downloading a job that isn't `Completed` → should 409 with a clear message.
- Kill the DB connection string temporarily and hit `/api/health` (should still return ok;
  it doesn't touch the DB) vs. `/api/jobs` (should return a clear 500, not a silent hang).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "No stored Google credentials for this user" on export-to-sheets | User signed in before this deploy's `GOOGLE_TOKEN_ENCRYPTION_KEY` was set, or the key rotated (old encrypted tokens become undecryptable — ask the user to reconnect Drive). |
| OAuth callback 400 "Invalid or expired OAuth state" | The `/api/auth/google/login` and `/callback` calls hit two different warm Lambda instances whose in-memory state caches differ; state entries also expire after 10 minutes. Retry sign-in. For a stronger guarantee, move `_oauth_states` to a DB-backed table. |
| Job stuck in "Processing" | Check Vercel function logs for the specific batch — a single corrupt file is caught and recorded as a `read_error` per-file, so a full stall usually means a Drive API auth/rate-limit issue; check for 401/429 in logs. |
| `psycopg2` connection errors on cold start | Confirm `DATABASE_URL` includes `?sslmode=require` if your Postgres host requires TLS (most managed providers do). |
| Company-name column not detected | Master sheet has an unrecognized header; resubmit the job with `field_overrides: {"company_name": "<actual header>"}` in the `POST /api/jobs` body. |

## Pre-launch checklist

- [ ] `npm run build` succeeds
- [ ] `python -m pytest backend_tests -q` passes
- [ ] `DATABASE_URL` set, tables created (check `/api/health` then create one test job)
- [ ] Google OAuth redirect URI matches production domain exactly
- [ ] `GOOGLE_TOKEN_ENCRYPTION_KEY` set and **backed up somewhere safe** (losing it makes
      all stored refresh tokens permanently undecryptable)
- [ ] CORS origin (`FRONTEND_URL`) matches the actual deployed frontend domain
- [ ] Ran one real consolidation job against the actual Drive folder and manually
      reviewed the Validation & Review / Matching Log sheets before treating the output
      as authoritative
- [ ] Confirmed `CRON_SECRET` is set if you don't want the cron endpoint publicly callable
