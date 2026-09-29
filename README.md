# Company Data Consolidation

Merges a master financial spreadsheet with per-company director/contact spreadsheets
(local folder or Google Drive) into one verified, validated Excel workbook:
`Final Consolidated Data`, `Validation & Review`, `Matching Log`, `Validation Summary`.

## How it works

```
Main Sheet/<master workbook>.xlsx      <- financial data (one row per company)
<Company A>.xlsx                       <- director list, company name comes from the filename
<Company B>.xlsx
...
```

1. **Master Sheet Reader** resolves the master workbook's columns to logical fields
   (`company_name`, `net_profit`, `revenue`, `ebitda`, `city`, `company_products`) using an
   exact-match-first synonym table (`api/_app/core/field_mapping.py`), so header variants
   like `"PAT "`, `"Total Revenue  *"`, `"EBITDA "` vs `"EBITDA %"` are resolved correctly
   without ever confusing an amount column with its margin/percent counterpart.
2. **Director Extractor** reads each company spreadsheet, strips DOB/placeholder artifacts
   from names, and extracts Name/Email/Phone (phone kept as text to preserve leading
   digits/country codes).
3. **Company Matcher** (`api/_app/core/matcher.py`) resolves each spreadsheet to a master
   row using a 4-level hierarchy: exact → normalized (suffix/punctuation-insensitive) →
   fuzzy (RapidFuzz) → manual review. Ambiguous or low-confidence matches are **never**
   auto-merged — they're flagged in `Validation & Review` and `Matching Log` instead.
4. **Consolidator** builds one row per master company, joining multiple directors with
   `; `-separated values while preserving positional alignment (director i's name/email/
   phone always stay together).
5. **Validator** runs the full checklist (duplicates, missing fields, unmatched
   files/companies, ambiguous matches, format errors) and produces a Validation Summary.
6. **Excel/Sheets Exporter** writes the final workbook, or creates a new Google
   Spreadsheet via the Sheets API — original source files are never modified.

## Project layout

```
app/                Next.js (App Router) frontend
components/         React components (progress, match table, summary cards)
lib/api.ts          Typed fetch client for the backend
api/
  index.py          Vercel Python entrypoint (imports the FastAPI app)
  requirements.txt
  _app/
    core/           Source-agnostic engine (mapping, normalizer, matcher, extractor,
                     consolidator, validator, excel/sheets exporters, local + Drive sources)
    db/             SQLAlchemy models + session (Postgres)
    jobs/           Chunked job state machine (Pending→...→Completed/Failed)
    auth/           Google OAuth, encrypted refresh tokens, session JWTs
    main.py         FastAPI routes
scripts/run_local.py   CLI: run the whole pipeline against a local folder, no server/DB needed
backend_tests/         pytest suite for normalization/matching/mapping/consolidation
sql/schema.sql          Reference Postgres schema (also auto-created by SQLAlchemy)
vercel.json             Function config + cron (chunk-advance safety net)
```

## Local development

### Backend engine (no server, no DB) — fastest way to test against your data

```bash
pip install -r api/requirements.txt
python scripts/run_local.py "path/to/Pune - Auto Ancillary (100)" output.xlsx
```

This prints the resolved column mapping, a validation summary, and writes the 4-sheet
workbook. Use this to sanity-check a new master-sheet format before wiring up the API.

### Backend tests

```bash
pip install -r api/requirements.txt pytest
python -m pytest backend_tests -q
```

### Full API + DB locally

> **`npm run dev` alone only serves the Next.js frontend.** Plain `next dev` has no
> knowledge of `api/index.py` — that Python function is only wired into `/api/**` by
> Vercel itself (`vercel dev` or an actual deployment). If you run just `npm run dev` and
> open the app, every `/api/*` call (job creation, Google login, etc.) will 404 even
> though the code is correct. Pick one of the two options below.

**Option A — one command, mirrors production exactly (recommended):**

```bash
npm install
pip install -r api/requirements.txt
export DATABASE_URL="sqlite:///./dev.db"   # or a real Postgres URL
export GOOGLE_TOKEN_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
npm run dev:full   # runs `vercel dev` (via npx) — serves Next.js AND api/index.py together on one port
```

**Option B — run the two servers separately:**

```bash
# Terminal 1 — the Python API
export DATABASE_URL="sqlite:///./dev.db"
export GOOGLE_TOKEN_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
cd api && uvicorn _app.main:app --reload --port 8000

# Terminal 2 — the frontend, pointed at that API
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm install
npm run dev   # http://localhost:3000
```

In production both deploy together on Vercel as one project (same origin), so
`NEXT_PUBLIC_API_URL` is left blank there — see `.env.example`.

## Google Cloud OAuth setup

1. Create a project at console.cloud.google.com, enable **Google Drive API** and
   **Google Sheets API**.
2. **OAuth consent screen**: External (or Internal for Workspace), add scopes
   `drive.readonly`, `drive.file`, `spreadsheets`, `userinfo.email`, `openid`.
3. **Credentials → Create OAuth client ID → Web application**.
   - Authorized redirect URI: `https://<your-vercel-domain>/api/auth/google/callback`
     (and `http://localhost:8000/api/auth/google/callback` for local dev).
4. Copy the Client ID/Secret into `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.
5. Generate `GOOGLE_TOKEN_ENCRYPTION_KEY`:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

See `.env.example` for the full variable list.

## Adding fields later (e.g. "Total Assets and Debt")

The mapping system is config-driven, not hardcoded:

1. Add synonyms to `FIELD_SYNONYMS` in `api/_app/core/field_mapping.py`
   (e.g. `"total_assets": ["total tangible assets", "total assets"]`).
2. Add the field to `REQUIRED_FIELDS` in `master_reader.py` and to the `CompanyRecord`
   / `ConsolidatedRow` dataclasses in `models.py`.
3. Add the column to `FINAL_COLUMNS` in `excel_exporter.py`.
4. Existing company-to-company alignment and validation logic need no changes — the
   pipeline is column-count agnostic beyond those four touch points.

Same pattern for new director fields (Designation, LinkedIn, Address are already wired
through `DIRECTOR_FIELD_SYNONYMS`, just add them to `FINAL_COLUMNS`/`ConsolidatedRow` to
surface them in the output).

## What has and hasn't been tested

- ✅ Full pipeline validated against the real 100-company dataset (`Pune - Auto Ancillary (100)`):
  90 exact matches, 7 normalized, 3 correctly-flagged high-confidence fuzzy matches, 0 silent
  mis-merges, 20/20 unit tests passing, `npm run build` compiles cleanly.
- ✅ Chunked job state machine (Pending→...→Completed) exercised end-to-end via the same
  SQLAlchemy models Postgres will use (tested against SQLite locally), including the
  manual-match override path.
- ⚠️ Google OAuth / Drive / Sheets integration is implemented but **not yet exercised with
  real Google credentials** — do this first against a test Drive folder before trusting it
  with production data (see DEPLOYMENT.md).
- ⚠️ Not yet deployed to Vercel/a live Postgres instance — see DEPLOYMENT.md for the exact
  steps and a verification checklist.
