import httpx
import pytest
from fastapi.testclient import TestClient

from app import drive, ratelimit
from app.main import app

from .conftest import UBL_XML

client = TestClient(app)
FOLDER = "1AbCdEfGhIjKlMnOpQrStUv"
FILE = "1ZyXwVuTsRqPoNmLkJiHgFe"


@pytest.mark.parametrize(
    "url, kind, id_, key",
    [
        (f"https://drive.google.com/drive/folders/{FOLDER}?usp=sharing", "folder", FOLDER, None),
        (f"https://drive.google.com/drive/u/0/folders/{FOLDER}", "folder", FOLDER, None),
        (f"https://drive.google.com/file/d/{FILE}/view?usp=drive_link", "file", FILE, None),
        (f"https://drive.google.com/open?id={FILE}", "file", FILE, None),
        (f"https://docs.google.com/document/d/{FILE}/edit", "file", FILE, None),
        (f"https://drive.google.com/file/d/{FILE}/view?resourcekey=0-abc_DEF", "file", FILE, "0-abc_DEF"),
    ],
)
def test_links_are_understood(url, kind, id_, key):
    link = drive.parse_link(url)
    assert (link.kind, link.id, link.resource_key) == (kind, id_, key)


@pytest.mark.parametrize("url", ["https://evil.example/drive/folders/1AbCdEfGhIjKl", "file:///etc/passwd", "https://drive.google.com/", "not a link"])
def test_other_links_are_refused(url):
    with pytest.raises(drive.DriveError):
        drive.parse_link(url)


@pytest.fixture
def google(monkeypatch):
    """Fake Drive API: a folder with a PDF, a photo, a Google Doc, an XML and an unsupported file."""
    requests: list[httpx.Request] = []
    files = [
        {"id": "pdfFile0001", "name": "b-invoice.pdf", "mimeType": "application/pdf", "size": "1200"},
        {"id": "jpgFile0001", "name": "a-receipt.jpg", "mimeType": "image/jpeg", "size": "900"},
        {"id": "docFile0001", "name": "c-quote", "mimeType": "application/vnd.google-apps.document"},
        {"id": "xmlFile0001", "name": "d-einvoice.xml", "mimeType": "application/xml", "size": "3000"},
        {"id": "zipFile0001", "name": "archive.zip", "mimeType": "application/zip", "size": "50"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        assert request.url.host == "www.googleapis.com"
        if path == "/drive/v3/files" and "pageToken" not in request.url.params:
            return httpx.Response(200, json={"files": files[:3], "nextPageToken": "p2"})
        if path == "/drive/v3/files":
            return httpx.Response(200, json={"files": files[3:]})
        if path == f"/drive/v3/files/{FILE}":
            return httpx.Response(200, json={"id": FILE, "name": "one.pdf", "mimeType": "application/pdf"})
        if path == "/drive/v3/files/xmlFile0001":
            return httpx.Response(200, content=UBL_XML)
        if path == "/drive/v3/files/docFile0001/export":
            return httpx.Response(200, content=b"%PDF-1.4 not really")
        return httpx.Response(404)

    monkeypatch.setattr(drive, "_http", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(ratelimit, "check", lambda ip: None)
    return requests


def test_folder_lists_supported_files_across_pages(google):
    response = client.post("/api/drive/list", json={"url": f"https://drive.google.com/drive/folders/{FOLDER}"})
    assert response.status_code == 200
    body = response.json()
    assert [f["name"] for f in body["files"]] == ["a-receipt.jpg", "b-invoice.pdf", "c-quote", "d-einvoice.xml"]
    assert body["skipped"] == 1
    assert all(r.url.params["key"] == "test-key" for r in google)


def test_single_file_link(google):
    body = client.post("/api/drive/list", json={"url": f"https://drive.google.com/file/d/{FILE}/view"}).json()
    assert body["files"] == [{"id": FILE, "name": "one.pdf", "mimeType": "application/pdf", "size": None, "resourceKey": None}]


def test_drive_file_is_downloaded_and_read(google):
    response = client.post("/api/drive/extract", json={"id": "xmlFile0001", "name": "d-einvoice.xml", "mimeType": "application/xml"})
    assert response.status_code == 200
    assert response.json()["source"] == "e-invoice"
    assert response.json()["data"]["total"] == 240
    assert google[-1].url.params["alt"] == "media"


def test_google_doc_is_exported_as_pdf(google, fake_ai):
    response = client.post("/api/drive/extract", json={"id": "docFile0001", "name": "c-quote", "mimeType": "application/vnd.google-apps.document"})
    assert google[-1].url.path.endswith("/export")
    assert google[-1].url.params["mimeType"] == "application/pdf"
    # The stub "PDF" is not a real PDF, so reading fails cleanly rather than crashing.
    assert response.status_code == 422
    assert "could not be opened" in response.json()["error"]


def test_private_file_explains_how_to_share(google):
    response = client.post("/api/drive/extract", json={"id": "privateFile1", "name": "x.pdf", "mimeType": "application/pdf"})
    assert response.status_code == 400
    assert "Anyone with the link" in response.json()["error"]


def test_without_api_key_drive_is_off(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(ratelimit, "check", lambda ip: None)
    assert client.get("/api/config").json()["googleDrive"] is False
    response = client.post("/api/drive/list", json={"url": f"https://drive.google.com/drive/folders/{FOLDER}"})
    assert response.status_code == 503
