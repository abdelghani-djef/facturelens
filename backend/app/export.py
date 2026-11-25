"""Excel export: one sheet of documents, one sheet of line items. Built in memory; nothing is stored."""

import io

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from pydantic import BaseModel

from .extract.schema import InvoiceData


class ExportRow(BaseModel):
    filename: str
    data: InvoiceData


DOC_COLUMNS = [
    ("File", lambda r: r.filename),
    ("Type", lambda r: r.data.document_type),
    ("Vendor", lambda r: r.data.vendor.name),
    ("Vendor tax ID", lambda r: r.data.vendor.tax_id),
    ("Customer", lambda r: r.data.customer.name),
    ("Number", lambda r: r.data.invoice_number),
    ("Date", lambda r: r.data.issue_date),
    ("Due date", lambda r: r.data.due_date),
    ("Currency", lambda r: r.data.currency),
    ("Subtotal", lambda r: r.data.subtotal),
    ("Tax", lambda r: r.data.tax_amount),
    ("Tax rate %", lambda r: r.data.tax_rate),
    ("Total", lambda r: r.data.total),
    ("Payment", lambda r: r.data.payment_method),
]
LINE_COLUMNS = ["File", "Vendor", "Number", "Description", "Quantity", "Unit price", "Amount"]


def to_xlsx(rows: list[ExportRow]) -> bytes:
    wb = Workbook()
    docs = wb.active
    docs.title = "Documents"
    docs.append([name for name, _ in DOC_COLUMNS])
    for row in rows:
        docs.append([get(row) for _, get in DOC_COLUMNS])

    lines = wb.create_sheet("Line items")
    lines.append(LINE_COLUMNS)
    for row in rows:
        for item in row.data.line_items:
            lines.append([row.filename, row.data.vendor.name, row.data.invoice_number,
                          item.description, item.quantity, item.unit_price, item.amount])

    for sheet in (docs, lines):
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"
        for i, column in enumerate(sheet.columns, start=1):
            width = max(len(str(c.value)) if c.value is not None else 0 for c in column)
            sheet.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 50)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
