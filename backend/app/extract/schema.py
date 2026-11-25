"""The shape of an extracted document, shared by every reader (e-invoice, PDF text, photo, OCR)."""

from typing import Literal

from pydantic import BaseModel, Field

DocumentType = Literal["invoice", "receipt", "credit_note", "other"]
Source = Literal["e-invoice", "pdf-text", "vision", "ocr"]


class Party(BaseModel):
    name: str | None = None
    tax_id: str | None = None
    address: str | None = None


class LineItem(BaseModel):
    description: str = ""
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class InvoiceData(BaseModel):
    document_type: DocumentType = "other"
    vendor: Party = Field(default_factory=Party)
    customer: Party = Field(default_factory=Party)
    invoice_number: str | None = None
    issue_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax_amount: float | None = None
    tax_rate: float | None = None
    total: float | None = None
    payment_method: str | None = None
    language: str | None = None


class Check(BaseModel):
    id: str
    ok: bool
    message: str


class ExtractResult(BaseModel):
    filename: str
    source: Source
    model: str | None = None
    data: InvoiceData
    checks: list[Check]
    status: Literal["ok", "review"]
    pages: int = 1
    warnings: list[str] = Field(default_factory=list)


def _nullable(kind: str) -> dict:
    return {"type": [kind, "null"]}


_PARTY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "tax_id", "address"],
    "properties": {"name": _nullable("string"), "tax_id": _nullable("string"), "address": _nullable("string")},
}

# Strict JSON schema sent to the AI: every property required, nothing extra. Mirrors InvoiceData.
AI_SCHEMA = {
    "name": "invoice_data",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "document_type", "vendor", "customer", "invoice_number", "issue_date", "due_date", "currency",
            "line_items", "subtotal", "tax_amount", "tax_rate", "total", "payment_method", "language",
        ],
        "properties": {
            "document_type": {"type": "string", "enum": ["invoice", "receipt", "credit_note", "other"]},
            "vendor": _PARTY,
            "customer": _PARTY,
            "invoice_number": _nullable("string"),
            "issue_date": _nullable("string"),
            "due_date": _nullable("string"),
            "currency": _nullable("string"),
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["description", "quantity", "unit_price", "amount"],
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": _nullable("number"),
                        "unit_price": _nullable("number"),
                        "amount": _nullable("number"),
                    },
                },
            },
            "subtotal": _nullable("number"),
            "tax_amount": _nullable("number"),
            "tax_rate": _nullable("number"),
            "total": _nullable("number"),
            "payment_method": _nullable("string"),
            "language": _nullable("string"),
        },
    },
}
