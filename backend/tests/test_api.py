import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app import ratelimit
from app.main import app

from .conftest import CII_XML, UBL_XML, blank_pdf, facturx_pdf, photo, text_pdf

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_rate_limit(monkeypatch):
    monkeypatch.setattr(ratelimit, "check", lambda ip: None)


def upload(name: str, content: bytes):
    return client.post("/api/extract", files={"file": (name, content)})


def test_xml_einvoice_needs_no_ai(fake_ai):
    response = upload("invoice.xml", UBL_XML)
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "e-invoice" and body["status"] == "ok"
    assert body["data"]["total"] == 240
    assert fake_ai == []


def test_factur_x_pdf_uses_embedded_xml(fake_ai):
    body = upload("facture.pdf", facturx_pdf(CII_XML)).json()
    assert body["source"] == "e-invoice"
    assert body["data"]["invoice_number"] == "FX-2026-042"
    assert fake_ai == []


def test_text_pdf_goes_to_text_model(fake_ai):
    pdf = text_pdf(["FACTURE N F-12", "Date 20/11/2026", "Item A 2 x 150,00 = 300,00", "Item B 1 x 400,00",
                    "Total HT 700,00 DA", "TVA 19% 133,00", "Total TTC 833,00 DA"])
    body = upload("facture.pdf", pdf).json()
    assert body["source"] == "pdf-text"
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["data"]["currency"] == "DZD"  # "DA" cleaned to the ISO code
    assert body["status"] == "ok"
    assert "Total TTC 833,00 DA" in fake_ai[0]["content"]


def test_scanned_pdf_and_photos_go_to_vision_model(fake_ai):
    for name, content in [("scan.pdf", blank_pdf()), ("receipt.jpg", photo()), ("shot.png", photo("PNG"))]:
        body = upload(name, content).json()
        assert body["source"] == "vision", name
    image_parts = [part for call in fake_ai for part in call["content"] if part["type"] == "image_url"]
    assert len(image_parts) == 3
    assert all(part["image_url"]["url"].startswith("data:image/jpeg;base64,") for part in image_parts)


def test_vision_unavailable_falls_back_to_ocr(monkeypatch, fake_ai):
    from app.extract import files
    from app.extract.groq import AIUnavailable

    async def chat_json(models, messages, schema, user):
        if any(m.id == "qwen/qwen3.8-27b" for m in models) and len(models) == 1:
            raise AIUnavailable("gone")
        fake_ai.append({"models": [m.id for m in models], "content": messages[1]["content"]})
        from .conftest import INVOICE_JSON
        return dict(INVOICE_JSON), models[0].id

    monkeypatch.setattr("app.extract.pipeline.chat_json", chat_json)
    monkeypatch.setattr(files, "ocr_text", lambda jpeg: "TOTAL TTC 833,00 DA date 20/11/2026")
    body = upload("receipt.jpg", photo()).json()
    assert body["source"] == "ocr"
    assert any("OCR" in w for w in body["warnings"])
    assert "TOTAL TTC 833,00" in fake_ai[-1]["content"]


def test_unsupported_and_oversized_files(fake_ai):
    response = upload("notes.txt", b"just some text")
    assert response.status_code == 415
    assert "not a PDF" in response.json()["error"]
    assert upload("other.xml", b"<catalog/>").status_code == 415
    big = b"%PDF" + b"0" * (10 * 1024 * 1024)
    assert upload("big.pdf", big).status_code == 413
    assert upload("empty.pdf", b"").status_code == 400


def test_ai_busy_returns_503(monkeypatch):
    from app.extract.groq import AIUnavailable

    async def busy(*args):
        raise AIUnavailable("rate limited", busy=True)

    monkeypatch.setattr("app.extract.pipeline.chat_json", busy)
    response = upload("doc.pdf", text_pdf(["Invoice", "x" * 100]))
    assert response.status_code == 503
    assert "busy" in response.json()["error"]


def test_excel_export(fake_ai):
    result = upload("invoice.xml", UBL_XML).json()
    response = client.post("/api/export/xlsx", json=[{"filename": result["filename"], "data": result["data"]}])
    assert response.status_code == 200
    wb = load_workbook(io.BytesIO(response.content))
    docs, lines = wb["Documents"], wb["Line items"]
    assert docs["C2"].value == "Seller SARL" and docs["M2"].value == 240
    assert lines["D2"].value == "Consulting day"


def test_rate_limit_message(monkeypatch):
    monkeypatch.setattr(ratelimit, "check", lambda ip: "Too many files in a short time. Please wait a few minutes.")
    response = upload("invoice.xml", UBL_XML)
    assert response.status_code == 429
    assert "Too many" in response.json()["error"]
