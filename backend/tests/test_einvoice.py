import pytest

from app.extract.einvoice import NotAnEInvoice, parse_einvoice
from app.extract.validate import run_checks, status_for

from .conftest import CII_XML, UBL_XML


def test_ubl_invoice_is_read_exactly():
    data = parse_einvoice(UBL_XML)
    assert data.document_type == "invoice"
    assert data.invoice_number == "INV-001"
    assert (data.issue_date, data.due_date, data.currency) == ("2026-10-01", "2026-10-31", "EUR")
    assert data.vendor.name == "Seller SARL"
    assert data.vendor.tax_id == "FR12345678901"
    assert data.vendor.address == "Lyon, FR"
    assert data.customer.name == "Buyer SAS"
    assert (data.subtotal, data.tax_amount, data.tax_rate, data.total) == (200, 40, 20, 240)
    assert data.payment_method == "SEPA credit transfer"
    [line] = data.line_items
    assert (line.description, line.quantity, line.unit_price, line.amount) == ("Consulting day", 2, 100, 200)
    assert status_for(run_checks(data)) == "ok"


def test_cii_factur_x_is_read_exactly():
    data = parse_einvoice(CII_XML)
    assert data.invoice_number == "FX-2026-042"
    assert (data.issue_date, data.due_date) == ("2026-11-05", "2026-12-05")
    assert data.vendor.name == "Hébergeur SAS"
    assert data.vendor.tax_id == "FR98765432109"
    assert data.customer.name == "Client SARL"
    assert (data.subtotal, data.tax_amount, data.tax_rate, data.total) == (120, 24, 20, 144)
    assert data.line_items[0].description == "Web hosting (1 year)"
    assert status_for(run_checks(data)) == "ok"


def test_credit_note():
    xml = UBL_XML.replace(b"<Invoice ", b"<CreditNote ").replace(b"</Invoice>", b"</CreditNote>")
    xml = xml.replace(b"InvoiceLine>", b"CreditNoteLine>").replace(b"InvoicedQuantity", b"CreditedQuantity")
    data = parse_einvoice(xml)
    assert data.document_type == "credit_note"
    assert data.line_items[0].quantity == 2


def test_other_xml_is_refused():
    with pytest.raises(NotAnEInvoice):
        parse_einvoice(b"<?xml version='1.0'?><catalog><book/></catalog>")


def test_hostile_xml_is_refused():
    bomb = b"""<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><Invoice>&b;</Invoice>"""
    with pytest.raises(NotAnEInvoice):
        parse_einvoice(bomb)
