"""Google Drive/Sheets connector: mirrors local_source.discover_local_folder but
against live Drive folders, and provides file download / Sheets export helpers.

Supports both uploaded .xlsx files (downloaded as bytes and read with pandas) and
native Google Sheets (read via the Sheets API, no download needed).
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FOLDER_MIME = "application/vnd.google-apps.folder"

EXCLUDE_NAME_HINTS = ("consolidated", "_output", "final consolidated")
MAX_RETRIES = 3


@dataclass
class DriveFileRef:
    file_id: str
    name: str
    mime_type: str


@dataclass
class DiscoveredDriveFolder:
    parent_folder_id: str
    master_file: DriveFileRef
    company_files: list[DriveFileRef]


def _with_retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except HttpError as exc:
            last_exc = exc
            if exc.resp is not None and exc.resp.status in (429, 500, 502, 503):
                time.sleep(2**attempt)
                continue
            raise
    raise last_exc


class DriveClient:
    def __init__(self, credentials: Credentials):
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self.sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def _list_children(self, folder_id: str) -> list[dict]:
        files: list[dict] = []
        page_token = None
        while True:
            resp = _with_retry(
                self.drive.files().list,
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
                pageSize=200,
            )
            result = resp.execute()
            files.extend(result.get("files", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return files

    def discover_folder(self, parent_folder_id: str) -> DiscoveredDriveFolder:
        children = self._list_children(parent_folder_id)

        main_sheet_folder = next(
            (c for c in children if c["mimeType"] == FOLDER_MIME and c["name"].strip().lower() == "main sheet"),
            None,
        )
        if not main_sheet_folder:
            raise FileNotFoundError("No 'Main Sheet' subfolder found in the selected Drive folder.")

        main_sheet_children = self._list_children(main_sheet_folder["id"])
        master_candidates = [
            c
            for c in main_sheet_children
            if c["mimeType"] in (GOOGLE_SHEET_MIME, XLSX_MIME) and not c["name"].startswith("~$")
        ]
        if not master_candidates:
            raise FileNotFoundError("No master spreadsheet found inside 'Main Sheet'.")
        master = master_candidates[0]
        master_file_name = master["name"].strip().lower()

        company_files = []
        for c in children:
            if c["mimeType"] == FOLDER_MIME:
                continue
            if c["mimeType"] not in (GOOGLE_SHEET_MIME, XLSX_MIME):
                continue
            if c["name"].startswith("~$"):
                continue
            if c["name"].strip().lower() == master_file_name:
                continue
            if any(hint in c["name"].lower() for hint in EXCLUDE_NAME_HINTS):
                continue
            company_files.append(DriveFileRef(c["id"], c["name"], c["mimeType"]))

        return DiscoveredDriveFolder(
            parent_folder_id=parent_folder_id,
            master_file=DriveFileRef(master["id"], master["name"], master["mimeType"]),
            company_files=sorted(company_files, key=lambda f: f.name),
        )

    def download_xlsx_bytes(self, file_id: str) -> bytes:
        """Downloads an uploaded .xlsx file's raw bytes."""
        request = self.drive.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = _with_retry(downloader.next_chunk)
        buf.seek(0)
        return buf.read()

    def export_native_sheet_as_xlsx(self, file_id: str) -> bytes:
        """Exports a native Google Sheet to .xlsx bytes so pandas/openpyxl can read it."""
        request = self.drive.files().export_media(fileId=file_id, mimeType=XLSX_MIME)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = _with_retry(downloader.next_chunk)
        buf.seek(0)
        return buf.read()

    def read_file_bytes(self, ref: DriveFileRef) -> bytes:
        if ref.mime_type == GOOGLE_SHEET_MIME:
            return self.export_native_sheet_as_xlsx(ref.file_id)
        return self.download_xlsx_bytes(ref.file_id)

    def create_spreadsheet_from_rows(self, title: str, sheets_data: dict[str, list[list]]) -> str:
        """Creates a new Google Spreadsheet with one tab per key in `sheets_data`,
        each value being a list of rows (first row = header). Returns the new
        spreadsheet's Drive file ID / URL-able ID.
        """
        sheet_specs = [{"properties": {"title": name}} for name in sheets_data.keys()]
        spreadsheet = _with_retry(
            self.sheets.spreadsheets().create,
            body={"properties": {"title": title}, "sheets": sheet_specs},
        ).execute()
        spreadsheet_id = spreadsheet["spreadsheetId"]

        data = []
        for sheet_name, rows in sheets_data.items():
            data.append({"range": f"'{sheet_name}'!A1", "values": rows})
        _with_retry(
            self.sheets.spreadsheets().values().batchUpdate,
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": data},
        ).execute()

        return spreadsheet_id
