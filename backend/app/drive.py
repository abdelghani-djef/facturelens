"""Reads invoices from a Google Drive file or folder link shared as "anyone with the link".

Uses the Drive API with an API key only (no sign-in), so it works for any visitor. Only
googleapis.com is ever called, with IDs that passed a strict pattern, so a pasted link can't make
the server fetch anything else.
"""

import os
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

API = "https://www.googleapis.com/drive/v3"
MAX_FILES = 25

_ID = r"[A-Za-z0-9_-]{10,}"
GOOGLE_DOC_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
}
SUPPORTED_TYPES = GOOGLE_DOC_TYPES | {
    "application/pdf", "application/xml", "text/xml",
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/tiff", "image/gif",
}


class DriveError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class DriveLink:
    kind: str  # "file" or "folder"
    id: str
    resource_key: str | None = None


@dataclass(frozen=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int | None
    resource_key: str | None = None


def api_key() -> str | None:
    return os.environ.get("GOOGLE_API_KEY") or None


def parse_link(url: str) -> DriveLink:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("drive.google.com", "docs.google.com"):
        raise DriveError("Paste a Google Drive link (drive.google.com or docs.google.com).")
    query = parse_qs(parsed.query)
    resource_key = (query.get("resourcekey") or [None])[0]

    if m := re.search(rf"/folders/({_ID})", parsed.path):
        return DriveLink("folder", m.group(1), resource_key)
    if m := re.search(rf"/d/({_ID})", parsed.path):
        return DriveLink("file", m.group(1), resource_key)
    ids = query.get("id") or []
    if ids and re.fullmatch(_ID, ids[0]):
        return DriveLink("file", ids[0], resource_key)
    raise DriveError("This doesn't look like a link to a Drive file or folder.")


_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "facturelens/0.1"})
    return _client


def _headers(link: DriveLink) -> dict[str, str]:
    return {"X-Goog-Drive-Resource-Keys": f"{link.id}/{link.resource_key}"} if link.resource_key else {}


def link_key(link: DriveLink, file_id: str) -> str | None:
    # A file link's own resource key applies to that file.
    return link.resource_key if link.kind == "file" and link.id == file_id else None


def _raise_for(response: httpx.Response, what: str) -> None:
    if response.status_code in (403, 404):
        raise DriveError(
            f"The {what} couldn't be opened. In Google Drive, share it as \"Anyone with the link\" and try again.",
            status=400,
        )
    if response.status_code == 429:
        raise DriveError("Google Drive is busy right now. Please try again in a minute.", status=503)
    if response.status_code == 400:
        # Almost always a missing, wrong or restricted API key on the server.
        raise DriveError("Google Drive import isn't working right now. Please upload the files instead.", status=503)
    if response.status_code >= 400:
        raise DriveError(f"Google Drive answered with an error ({response.status_code}).", status=502)


def _require_key() -> str:
    key = api_key()
    if not key:
        raise DriveError("Google Drive import isn't set up on this server.", status=503)
    return key


async def list_files(link: DriveLink) -> tuple[list[DriveFile], int]:
    """Supported files behind the link, and how many others were skipped."""
    key = _require_key()
    fields = "id,name,mimeType,size,resourceKey"
    if link.kind == "file":
        response = await _http().get(
            f"{API}/files/{link.id}", headers=_headers(link),
            params={"fields": fields, "supportsAllDrives": "true", "key": key},
        )
        _raise_for(response, "file")
        items = [response.json()]
    else:
        items, token = [], None
        while len(items) < 500:
            params = {
                "q": f"'{link.id}' in parents and trashed = false",
                "fields": f"nextPageToken,files({fields})",
                "pageSize": "100", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true", "key": key,
            }
            if token:
                params["pageToken"] = token
            response = await _http().get(f"{API}/files", headers=_headers(link), params=params)
            _raise_for(response, "folder")
            body = response.json()
            items += body.get("files", [])
            token = body.get("nextPageToken")
            if not token:
                break

    supported = [
        DriveFile(i["id"], i.get("name") or "document", i.get("mimeType", ""),
                  int(i["size"]) if i.get("size") else None, i.get("resourceKey") or link_key(link, i["id"]))
        for i in items
        if i.get("mimeType") in SUPPORTED_TYPES
    ]
    supported.sort(key=lambda f: f.name.lower())
    skipped = len(items) - len(supported) + max(0, len(supported) - MAX_FILES)
    return supported[:MAX_FILES], skipped


async def download(file_id: str, mime_type: str, max_bytes: int, resource_key: str | None = None) -> tuple[bytes, str]:
    """The file's bytes (Google Docs exported as PDF) and the name suffix to use."""
    if not re.fullmatch(_ID, file_id) or (resource_key and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", resource_key)):
        raise DriveError("Invalid Drive file id.")
    headers = {"X-Goog-Drive-Resource-Keys": f"{file_id}/{resource_key}"} if resource_key else {}
    key = _require_key()
    if mime_type in GOOGLE_DOC_TYPES:
        url, params, suffix = f"{API}/files/{file_id}/export", {"mimeType": "application/pdf", "key": key}, ".pdf"
    else:
        url, params, suffix = f"{API}/files/{file_id}", {"alt": "media", "supportsAllDrives": "true", "key": key}, ""

    async with _http().stream("GET", url, params=params, headers=headers) as response:
        if response.status_code >= 400:
            await response.aread()
            _raise_for(response, "file")
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > max_bytes:
                raise DriveError(f"This Drive file is larger than {max_bytes // (1024 * 1024)} MB.", status=413)
            chunks.append(chunk)
    return b"".join(chunks), suffix
