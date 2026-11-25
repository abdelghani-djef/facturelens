"""Cleans the extracted values and checks that the numbers add up."""

import datetime as dt
import re

from .schema import Check, InvoiceData

_CURRENCY_ALIASES = {
    "DA": "DZD", "دج": "DZD", "دينار": "DZD", "€": "EUR", "EURO": "EUR", "EUROS": "EUR",
    "$": "USD", "£": "GBP", "DH": "MAD", "MAD": "MAD", "DT": "TND",
}


def clean(data: InvoiceData) -> InvoiceData:
    if data.currency:
        code = data.currency.strip().upper()
        data.currency = _CURRENCY_ALIASES.get(code, code)[:3] if code else None
    if data.language:
        data.language = data.language.strip().lower()[:2] or None
    data.line_items = [item for item in data.line_items if item.description.strip() or item.amount is not None]
    for field in ("subtotal", "tax_amount", "total"):
        value = getattr(data, field)
        if value is not None:
            setattr(data, field, round(value, 2))
    return data


def _close(a: float, b: float, reference: float | None = None) -> bool:
    scale = abs(reference if reference is not None else max(abs(a), abs(b)))
    return abs(a - b) <= max(0.02, scale * 0.005)


def _fmt(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _valid_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        return False
    return dt.date(2000, 1, 1) <= day <= dt.date.today() + dt.timedelta(days=366)


def run_checks(data: InvoiceData) -> list[Check]:
    checks: list[Check] = []

    if data.total is None:
        checks.append(Check(id="total", ok=False, message="No total found."))
    else:
        checks.append(Check(id="total", ok=True, message=f"Total found: {_fmt(data.total)}."))

    if data.issue_date:
        ok = _valid_date(data.issue_date)
        checks.append(Check(id="date", ok=ok, message="Date looks valid." if ok else f"Date {data.issue_date} looks wrong."))
    else:
        checks.append(Check(id="date", ok=False, message="No date found."))

    bad_lines = [
        item.description or f"line {i + 1}"
        for i, item in enumerate(data.line_items)
        if None not in (item.quantity, item.unit_price, item.amount)
        and not _close(item.quantity * item.unit_price, item.amount)  # type: ignore[operator]
    ]
    if bad_lines:
        checks.append(Check(id="line_math", ok=False,
                            message=f"Quantity × unit price doesn't match the amount on: {', '.join(bad_lines[:3])}."))

    amounts = [item.amount for item in data.line_items if item.amount is not None]
    if amounts and len(amounts) == len(data.line_items):
        lines_sum = sum(amounts)
        targets = [t for t in (data.subtotal, data.total) if t is not None]
        if targets:
            ok = any(_close(lines_sum, t) for t in targets)
            checks.append(Check(
                id="lines_sum", ok=ok,
                message=f"Line items add up to {_fmt(lines_sum)}." if ok
                else f"Line items add up to {_fmt(lines_sum)}, which matches neither the subtotal nor the total.",
            ))

    if None not in (data.subtotal, data.tax_amount, data.total):
        expected = data.subtotal + data.tax_amount  # type: ignore[operator]
        ok = _close(expected, data.total, data.total)  # type: ignore[arg-type]
        checks.append(Check(
            id="tax_math", ok=ok,
            message="Subtotal + tax = total." if ok
            else f"Subtotal + tax = {_fmt(expected)}, but the total is {_fmt(data.total)}.",  # type: ignore[arg-type]
        ))

    return checks


def status_for(checks: list[Check]) -> str:
    return "ok" if all(check.ok for check in checks) else "review"
