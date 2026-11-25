"""Turns one uploaded file into structured invoice data.

E-invoice XML (alone or inside a Factur-X PDF) is read exactly. A PDF with text goes to a text model.
Photos, screenshots and scanned PDFs go to a vision model; if it is unavailable, OCR text goes to a text model.
"""

import asyncio
import base64
import logging

from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from . import files
from .einvoice import NotAnEInvoice, parse_einvoice
from .groq import TEXT_MODELS, VISION_MODELS, AIUnavailable, chat_json
from .prompt import SYSTEM_PROMPT
from .schema import AI_SCHEMA, ExtractResult, InvoiceData, Source
from .validate import clean, run_checks, status_for

log = logging.getLogger("facturelens.pipeline")

MIN_PDF_TEXT = 80  # characters; below this a PDF is treated as scanned
MAX_TEXT = 24_000  # characters sent to the AI

# Images are expensive in AI tokens, so one image request at a time keeps under the per-minute limit.
_vision_slot = asyncio.Semaphore(1)


class ExtractionFailed(Exception):
    def __init__(self, message: str, busy: bool = False):
        super().__init__(message)
        self.busy = busy


async def extract(filename: str, content: bytes, user: str) -> ExtractResult:
    kind = files.detect_kind(content, filename)
    warnings: list[str] = []
    pages = 1
    model: str | None = None

    if kind == "xml":
        try:
            data = parse_einvoice(content)
        except NotAnEInvoice as error:
            raise files.UnsupportedFile(
                "This XML file is not a UBL or CII (Factur-X) e-invoice."
            ) from error
        source: Source = "e-invoice"

    elif kind == "pdf":
        embedded = await run_in_threadpool(files.pdf_embedded_xml, content)
        data = None
        if embedded:
            try:
                data, source = parse_einvoice(embedded), "e-invoice"
            except NotAnEInvoice:
                warnings.append("The PDF has an attached XML file that is not a readable e-invoice; read the PDF instead.")
        if data is None:
            try:
                text, pages = await run_in_threadpool(files.pdf_text, content)
            except Exception as error:
                raise ExtractionFailed("This PDF could not be opened. It may be damaged or password-protected.") from error
            if len(text) >= MIN_PDF_TEXT:
                data, model = await _from_text(text, user, warnings)
                source = "pdf-text"
            else:
                images = await run_in_threadpool(files.pdf_page_images, content)
                if pages > len(images):
                    warnings.append(f"Only the first {len(images)} of {pages} pages were read.")
                data, model, source = await _from_images(images, user, warnings)

    else:
        try:
            jpeg = await run_in_threadpool(files.prepare_image, content)
        except Exception as error:
            raise ExtractionFailed("This image could not be opened.") from error
        data, model, source = await _from_images([jpeg], user, warnings)

    data = clean(data)
    checks = run_checks(data)
    return ExtractResult(
        filename=filename, source=source, model=model, data=data, checks=checks,
        status=status_for(checks), pages=pages, warnings=warnings,  # type: ignore[arg-type]
    )


async def _ask(models, content, user: str) -> tuple[InvoiceData, str]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]
    raw, model = await chat_json(models, messages, AI_SCHEMA, user)
    try:
        return InvoiceData.model_validate(raw), model
    except ValidationError as error:
        log.warning("model %s returned data outside the schema: %s", model, error.error_count())
        raise AIUnavailable("the AI's answer did not match the expected format") from error


async def _from_text(text: str, user: str, warnings: list[str]) -> tuple[InvoiceData, str]:
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT]
        warnings.append("The document is long; only its beginning was read.")
    content = f"Extract the data from this document.\n\n<document>\n{text}\n</document>"
    try:
        return await _ask(TEXT_MODELS, content, user)
    except AIUnavailable as error:
        raise ExtractionFailed(_busy_message(error), busy=error.busy) from error


async def _from_images(images: list[bytes], user: str, warnings: list[str]) -> tuple[InvoiceData, str, Source]:
    content = [{"type": "text", "text": "Extract the data from this document. Its pages are attached in order."}]
    content += [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(img).decode()}"}}
        for img in images
    ]
    try:
        async with _vision_slot:
            data, model = await _ask(VISION_MODELS, content, user)
        return data, model, "vision"
    except AIUnavailable as error:
        log.info("vision unavailable (%s); trying OCR", error)
        vision_error = error

    try:
        texts = [await run_in_threadpool(files.ocr_text, img) for img in images]
    except files.OCRUnavailable as error:
        log.warning("OCR unavailable: %s", error)
        raise ExtractionFailed(_busy_message(vision_error), busy=vision_error.busy) from error

    text = "\n\n".join(t.strip() for t in texts if t.strip())
    if len(text) < 20:
        raise ExtractionFailed("No readable text was found. Try a sharper, well-lit photo.")
    warnings.append("Read with text recognition (OCR) because the image AI was unavailable; check the values.")
    data, model = await _from_text(text, user, warnings)
    return data, model, "ocr"


def _busy_message(error: AIUnavailable) -> str:
    if error.busy:
        return "The AI is busy right now. Please try again in a minute."
    return "The AI could not read this document. Please try again."
