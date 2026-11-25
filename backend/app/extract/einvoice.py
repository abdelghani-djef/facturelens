"""Reads structured e-invoices exactly, without AI.

Supports the two European standard syntaxes (EN 16931):
- UBL 2.1 (Invoice / CreditNote), used by Peppol and many e-invoicing platforms;
- UN/CEFACT CII (CrossIndustryInvoice), the XML inside Factur-X and ZUGFeRD PDFs.
Parsing is namespace-agnostic and uses defusedxml, so hostile XML (entity bombs, external entities) is refused.
"""

from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring

from .schema import InvoiceData, LineItem, Party


class NotAnEInvoice(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _all(el: Element | None, path: str) -> list[Element]:
    if el is None:
        return []
    current = [el]
    for part in path.split("/"):
        current = [child for node in current for child in node if _local(child.tag) == part]
        if not current:
            return []
    return current


def _first(el: Element | None, path: str) -> Element | None:
    found = _all(el, path)
    return found[0] if found else None


def _text(el: Element | None, *paths: str) -> str | None:
    for path in paths:
        node = _first(el, path)
        if node is not None and node.text and node.text.strip():
            return node.text.strip()
    return None


def _num(el: Element | None, *paths: str) -> float | None:
    value = _text(el, *paths)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _join(*parts: str | None) -> str | None:
    joined = ", ".join(p for p in parts if p)
    return joined or None


def _cii_date(value: str | None) -> str | None:
    # CII dates use format 102: YYYYMMDD.
    if value and len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


# UNCL 4461 payment means codes most often seen on invoices.
_PAYMENT_MEANS = {
    "10": "cash", "20": "cheque", "30": "credit transfer", "31": "debit transfer", "42": "bank transfer",
    "48": "card", "49": "direct debit", "57": "standing agreement", "58": "SEPA credit transfer",
    "59": "SEPA direct debit", "68": "online payment",
}


def parse_einvoice(xml: bytes) -> InvoiceData:
    try:
        root = fromstring(xml)
    except Exception as error:  # defusedxml raises several error types
        raise NotAnEInvoice(f"not readable XML: {type(error).__name__}") from error

    name = _local(root.tag)
    if name in ("Invoice", "CreditNote"):
        return _parse_ubl(root, credit=name == "CreditNote")
    if name == "CrossIndustryInvoice":
        return _parse_cii(root)
    raise NotAnEInvoice(f"unknown XML document <{name}>")


def _ubl_party(party: Element | None) -> Party:
    return Party(
        name=_text(party, "PartyLegalEntity/RegistrationName", "PartyName/Name"),
        tax_id=_text(party, "PartyTaxScheme/CompanyID", "PartyLegalEntity/CompanyID", "PartyIdentification/ID"),
        address=_join(
            _text(party, "PostalAddress/StreetName"),
            _text(party, "PostalAddress/CityName"),
            _text(party, "PostalAddress/PostalZone"),
            _text(party, "PostalAddress/Country/IdentificationCode"),
        ),
    )


def _parse_ubl(root: Element, credit: bool) -> InvoiceData:
    line_tag, qty_tag = ("CreditNoteLine", "CreditedQuantity") if credit else ("InvoiceLine", "InvoicedQuantity")
    rates = {_text(sub, "TaxCategory/Percent") for sub in _all(root, "TaxTotal/TaxSubtotal")} - {None}
    means = _text(root, "PaymentMeans/PaymentMeansCode")
    type_code = _text(root, "InvoiceTypeCode", "CreditNoteTypeCode")
    return InvoiceData(
        document_type="credit_note" if credit or type_code == "381" else "invoice",
        vendor=_ubl_party(_first(root, "AccountingSupplierParty/Party")),
        customer=_ubl_party(_first(root, "AccountingCustomerParty/Party")),
        invoice_number=_text(root, "ID"),
        issue_date=_text(root, "IssueDate"),
        due_date=_text(root, "DueDate", "PaymentMeans/PaymentDueDate"),
        currency=_text(root, "DocumentCurrencyCode"),
        line_items=[
            LineItem(
                description=_text(line, "Item/Name", "Item/Description") or "",
                quantity=_num(line, qty_tag),
                unit_price=_num(line, "Price/PriceAmount"),
                amount=_num(line, "LineExtensionAmount"),
            )
            for line in _all(root, line_tag)
        ],
        subtotal=_num(root, "LegalMonetaryTotal/TaxExclusiveAmount"),
        tax_amount=_num(root, "TaxTotal/TaxAmount"),
        tax_rate=float(rates.pop()) if len(rates) == 1 else None,
        total=_num(root, "LegalMonetaryTotal/TaxInclusiveAmount", "LegalMonetaryTotal/PayableAmount"),
        payment_method=_PAYMENT_MEANS.get(means or "", means),
        language=None,
    )


def _cii_party(party: Element | None) -> Party:
    return Party(
        name=_text(party, "Name"),
        tax_id=_text(party, "SpecifiedTaxRegistration/ID", "SpecifiedLegalOrganization/ID"),
        address=_join(
            _text(party, "PostalTradeAddress/LineOne"),
            _text(party, "PostalTradeAddress/CityName"),
            _text(party, "PostalTradeAddress/PostcodeCode"),
            _text(party, "PostalTradeAddress/CountryID"),
        ),
    )


def _parse_cii(root: Element) -> InvoiceData:
    doc = _first(root, "ExchangedDocument")
    tx = _first(root, "SupplyChainTradeTransaction")
    agreement = _first(tx, "ApplicableHeaderTradeAgreement")
    settlement = _first(tx, "ApplicableHeaderTradeSettlement")
    sums = _first(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation")
    rates = {_text(tax, "RateApplicablePercent") for tax in _all(settlement, "ApplicableTradeTax")} - {None}
    means = _text(settlement, "SpecifiedTradeSettlementPaymentMeans/TypeCode")
    type_code = _text(doc, "TypeCode")
    return InvoiceData(
        document_type="credit_note" if type_code == "381" else "invoice",
        vendor=_cii_party(_first(agreement, "SellerTradeParty")),
        customer=_cii_party(_first(agreement, "BuyerTradeParty")),
        invoice_number=_text(doc, "ID"),
        issue_date=_cii_date(_text(doc, "IssueDateTime/DateTimeString")),
        due_date=_cii_date(_text(settlement, "SpecifiedTradePaymentTerms/DueDateDateTime/DateTimeString")),
        currency=_text(settlement, "InvoiceCurrencyCode"),
        line_items=[
            LineItem(
                description=_text(line, "SpecifiedTradeProduct/Name") or "",
                quantity=_num(line, "SpecifiedLineTradeDelivery/BilledQuantity"),
                unit_price=_num(line, "SpecifiedLineTradeAgreement/NetPriceProductTradePrice/ChargeAmount"),
                amount=_num(line, "SpecifiedLineTradeSettlement/SpecifiedTradeSettlementLineMonetarySummation/LineTotalAmount"),
            )
            for line in _all(tx, "IncludedSupplyChainTradeLineItem")
        ],
        subtotal=_num(sums, "TaxBasisTotalAmount"),
        tax_amount=_num(sums, "TaxTotalAmount"),
        tax_rate=float(rates.pop()) if len(rates) == 1 else None,
        total=_num(sums, "GrandTotalAmount", "DuePayableAmount"),
        payment_method=_PAYMENT_MEANS.get(means or "", means),
        language=None,
    )
