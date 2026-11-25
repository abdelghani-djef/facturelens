import asyncio
import hashlib
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import drive, ratelimit
from .export import ExportRow, to_xlsx
from .extract.files import UnsupportedFile
from .extract.pipeline import ExtractionFailed, extract
from .extract.schema import ExtractResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

MAX_FILE_BYTES = 10 * 1024 * 1024
# Two documents at a time keeps memory low on a small server; others wait their turn.
_slots = asyncio.Semaphore(int(os.environ.get("MAX_PARALLEL", "2")))

app = FastAPI(title="FactureLens", docs_url=None, redoc_url=None, openapi_url=None)


def _client_ip(request: Request) -> str:
    # Behind Caddy, which sets X-Forwarded-For from the real connection.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/config")
def config() -> dict:
    return {"maxFileMb": MAX_FILE_BYTES // (1024 * 1024), "googleDrive": drive.api_key() is not None}


@app.post("/api/extract", response_model=ExtractResult)
async def extract_file(request: Request, file: UploadFile) -> ExtractResult:
    ip = _client_ip(request)
    if reason := ratelimit.check(ip):
        raise HTTPException(429, reason)

    content = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, f"Files must be {MAX_FILE_BYTES // (1024 * 1024)} MB or smaller.")
    if not content:
        raise HTTPException(400, "The file is empty.")

    return await _read(Path(file.filename or "document").name[:200], content, ip)


async def _read(filename: str, content: bytes, ip: str) -> ExtractResult:
    # Groq gets a hash of the visitor's IP for abuse monitoring, never the address itself.
    user = hashlib.sha256(ip.encode()).hexdigest()[:16]
    try:
        async with _slots:
            return await extract(filename, content, user)
    except UnsupportedFile as error:
        raise HTTPException(415, str(error)) from error
    except ExtractionFailed as error:
        raise HTTPException(503 if error.busy else 422, str(error)) from error
    finally:
        del content  # nothing about the file is kept


class DriveListRequest(BaseModel):
    url: str = Field(max_length=2000)


class DriveFileRequest(BaseModel):
    id: str = Field(max_length=200)
    name: str = Field(max_length=300)
    mimeType: str = Field(max_length=200)
    resourceKey: str | None = Field(default=None, max_length=100)


@app.post("/api/drive/list")
async def drive_list(request: Request, body: DriveListRequest) -> dict:
    if reason := ratelimit.check(_client_ip(request)):
        raise HTTPException(429, reason)
    try:
        files, skipped = await drive.list_files(drive.parse_link(body.url))
    except drive.DriveError as error:
        raise HTTPException(error.status, str(error)) from error
    if not files:
        raise HTTPException(400, "No PDFs, images or XML e-invoices were found behind this link.")
    return {
        "files": [{"id": f.id, "name": f.name, "mimeType": f.mime_type, "size": f.size, "resourceKey": f.resource_key} for f in files],
        "skipped": skipped,
    }


@app.post("/api/drive/extract", response_model=ExtractResult)
async def drive_extract(request: Request, body: DriveFileRequest) -> ExtractResult:
    ip = _client_ip(request)
    if reason := ratelimit.check(ip):
        raise HTTPException(429, reason)
    try:
        content, suffix = await drive.download(body.id, body.mimeType, MAX_FILE_BYTES, body.resourceKey)
    except drive.DriveError as error:
        raise HTTPException(error.status, str(error)) from error
    name = Path(body.name).name[:200] or "document"
    if suffix and not name.lower().endswith(suffix):
        name += suffix
    return await _read(name, content, ip)


@app.post("/api/export/xlsx")
def export_xlsx(rows: list[ExportRow]) -> Response:
    if not rows or len(rows) > 2000:
        raise HTTPException(400, "Send between 1 and 2000 documents.")
    return Response(
        to_xlsx(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="facturelens-export.xlsx"'},
    )


@app.exception_handler(HTTPException)
async def http_error(_: Request, error: HTTPException) -> JSONResponse:
    return JSONResponse({"error": error.detail}, status_code=error.status_code)


# The built React app, served from the same container in production.
_static = Path(os.environ.get("STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if _static.is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")
