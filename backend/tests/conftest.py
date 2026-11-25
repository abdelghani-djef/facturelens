import io

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

UBL_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>INV-001</cbc:ID>
  <cbc:IssueDate>2026-10-01</cbc:IssueDate>
  <cbc:DueDate>2026-10-31</cbc:DueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty><cac:Party>
    <cac:PartyName><cbc:Name>Seller SARL</cbc:Name></cac:PartyName>
    <cac:PostalAddress><cbc:CityName>Lyon</cbc:CityName><cac:Country><cbc:IdentificationCode>FR</cbc:IdentificationCode></cac:Country></cac:PostalAddress>
    <cac:PartyTaxScheme><cbc:CompanyID>FR12345678901</cbc:CompanyID></cac:PartyTaxScheme>
  </cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party><cac:PartyName><cbc:Name>Buyer SAS</cbc:Name></cac:PartyName></cac:Party></cac:AccountingCustomerParty>
  <cac:PaymentMeans><cbc:PaymentMeansCode>58</cbc:PaymentMeansCode></cac:PaymentMeans>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="EUR">40.00</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="EUR">200.00</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="EUR">40.00</cbc:TaxAmount>
      <cac:TaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>20</cbc:Percent></cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:TaxExclusiveAmount currencyID="EUR">200.00</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="EUR">240.00</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">240.00</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="C62">2</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="EUR">200.00</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>Consulting day</cbc:Name></cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="EUR">100.00</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>"""

CII_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext><ram:GuidelineSpecifiedDocumentContextParameter><ram:ID>urn:cen.eu:en16931:2017</ram:ID></ram:GuidelineSpecifiedDocumentContextParameter></rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>FX-2026-042</ram:ID><ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime><udt:DateTimeString format="102">20261105</udt:DateTimeString></ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:SpecifiedTradeProduct><ram:Name>Web hosting (1 year)</ram:Name></ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement><ram:NetPriceProductTradePrice><ram:ChargeAmount>120.00</ram:ChargeAmount></ram:NetPriceProductTradePrice></ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery><ram:BilledQuantity unitCode="C62">1</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement><ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>120.00</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation></ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Hébergeur SAS</ram:Name>
        <ram:PostalTradeAddress><ram:CityName>Paris</ram:CityName><ram:CountryID>FR</ram:CountryID></ram:PostalTradeAddress>
        <ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">FR98765432109</ram:ID></ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty><ram:Name>Client SARL</ram:Name></ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementPaymentMeans><ram:TypeCode>58</ram:TypeCode></ram:SpecifiedTradeSettlementPaymentMeans>
      <ram:ApplicableTradeTax><ram:CalculatedAmount>24.00</ram:CalculatedAmount><ram:TypeCode>VAT</ram:TypeCode><ram:BasisAmount>120.00</ram:BasisAmount><ram:CategoryCode>S</ram:CategoryCode><ram:RateApplicablePercent>20</ram:RateApplicablePercent></ram:ApplicableTradeTax>
      <ram:SpecifiedTradePaymentTerms><ram:DueDateDateTime><udt:DateTimeString format="102">20261205</udt:DateTimeString></ram:DueDateDateTime></ram:SpecifiedTradePaymentTerms>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>120.00</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">24.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>144.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>144.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>""".encode()


def text_pdf(lines: list[str]) -> bytes:
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(60, y, line)
        y -= 22
    c.showPage()
    c.save()
    return out.getvalue()


def blank_pdf() -> bytes:
    """A page with no text layer, like a scan."""
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    c.rect(60, 600, 200, 100, fill=1)
    c.showPage()
    c.save()
    return out.getvalue()


def facturx_pdf(xml: bytes) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(text_pdf(["Invoice FX-2026-042", "Total 144.00 EUR"]))))
    writer.add_attachment("factur-x.xml", xml)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def photo(fmt: str = "JPEG") -> bytes:
    img = Image.new("RGB", (600, 400), "white")
    ImageDraw.Draw(img).text((40, 40), "TOTAL 700.00", fill="black")
    out = io.BytesIO()
    img.save(out, format=fmt)
    return out.getvalue()


INVOICE_JSON = {
    "document_type": "invoice",
    "vendor": {"name": "Shop", "tax_id": "NIF 0001", "address": None},
    "customer": {"name": None, "tax_id": None, "address": None},
    "invoice_number": "F-12",
    "issue_date": "2026-11-20",
    "due_date": None,
    "currency": "DA",
    "line_items": [
        {"description": "Item A", "quantity": 2, "unit_price": 150, "amount": 300},
        {"description": "Item B", "quantity": 1, "unit_price": 400, "amount": 400},
    ],
    "subtotal": 700,
    "tax_amount": 133,
    "tax_rate": 19,
    "total": 833,
    "payment_method": "cash",
    "language": "fr",
}


@pytest.fixture
def fake_ai(monkeypatch):
    """Replaces Groq with a stub that records what it was sent."""
    calls: list[dict] = []

    async def fake_chat_json(models, messages, schema, user):
        calls.append({"models": [m.id for m in models], "content": messages[1]["content"]})
        return dict(INVOICE_JSON), models[0].id

    monkeypatch.setattr("app.extract.pipeline.chat_json", fake_chat_json)
    return calls
