from app.extract.schema import InvoiceData, LineItem
from app.extract.validate import clean, run_checks, status_for


def checks_by_id(data: InvoiceData) -> dict[str, bool]:
    return {check.id: check.ok for check in run_checks(data)}


def test_consistent_invoice_passes():
    data = InvoiceData(
        issue_date="2026-11-20", subtotal=700, tax_amount=133, total=833,
        line_items=[LineItem(description="A", quantity=2, unit_price=150, amount=300),
                    LineItem(description="B", quantity=1, unit_price=400, amount=400)],
    )
    assert checks_by_id(data) == {"total": True, "date": True, "lines_sum": True, "tax_math": True}
    assert status_for(run_checks(data)) == "ok"


def test_unit_price_mistaken_for_amount_is_flagged():
    # The mistake seen in testing: "2 x 150.00" read as amount 150.
    data = InvoiceData(issue_date="2026-11-20", total=700,
                       line_items=[LineItem(description="A", quantity=2, unit_price=150, amount=150),
                                   LineItem(description="B", quantity=1, unit_price=400, amount=400)])
    ids = checks_by_id(data)
    assert ids["line_math"] is False
    assert ids["lines_sum"] is False
    assert status_for(run_checks(data)) == "review"


def test_tax_mismatch_and_missing_values():
    data = InvoiceData(subtotal=100, tax_amount=19, total=200)
    ids = checks_by_id(data)
    assert ids["tax_math"] is False
    assert ids["date"] is False
    assert status_for(run_checks(InvoiceData())) == "review"


def test_receipt_lines_including_tax_match_total():
    data = InvoiceData(issue_date="2026-01-05", subtotal=None, total=119,
                       line_items=[LineItem(description="Coffee", amount=119)])
    assert checks_by_id(data)["lines_sum"] is True


def test_impossible_date_is_flagged():
    assert checks_by_id(InvoiceData(issue_date="2026-02-30", total=1))["date"] is False
    assert checks_by_id(InvoiceData(issue_date="1990-01-01", total=1))["date"] is False


def test_clean_normalizes_currency_and_language():
    data = clean(InvoiceData(currency=" da ", language="FR-fr", total=10.004,
                             line_items=[LineItem(description=" ", amount=None), LineItem(description="x")]))
    assert (data.currency, data.language, data.total) == ("DZD", "fr", 10.0)
    assert [item.description for item in data.line_items] == ["x"]
    assert clean(InvoiceData(currency="€")).currency == "EUR"
