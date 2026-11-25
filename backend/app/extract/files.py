"""File handling: detecting the type, reading PDFs, preparing images for the AI, and OCR."""

import io
import logging
from typing import Literal

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from pypdf import PdfReader

log = logging.getLogger("facturelens.files")

register_heif_opener()  # iPhone photos (HEIC/HEIF)
Image.MAX_IMAGE_PIXELS = 60_000_000  # refuse decompression bombs

Kind = Literal["pdf", "xml", "image"]

# Pixels on the long side: sharp enough to read receipt print, and about half the AI tokens of 2000 px
# (image tokens grow with the pixel count, and the free tier allows few tokens a minute).
MAX_IMAGE_SIDE = 1600
MAX_AI_PAGES = 3  # pages of a scanned PDF sent to the AI


class UnsupportedFile(ValueError):
    pass


def detect_kind(content: bytes, filename: str) -> Kind:
    head = content[:64].lstrip(b"\xef\xbb\xbf \t\r\n")
    if content.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"<?xml") or head.startswith(b"<"):
        return "xml"
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        return "image"
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise UnsupportedFile(
            f"{filename or 'This file'} is not a PDF, an image or an XML e-invoice."
        ) from error


def pdf_text(content: bytes, max_pages: int = 10) -> tuple[str, int]:
    """Text of the first pages and the page count. Empty text means a scanned (image-only) PDF."""
    pdf = pdfium.PdfDocument(content)
    try:
        pages = len(pdf)
        parts = []
        for i in range(min(pages, max_pages)):
            page = pdf[i]
            textpage = page.get_textpage()
            parts.append(textpage.get_text_bounded())
            textpage.close()
            page.close()
        return "\n\n".join(parts).strip(), pages
    finally:
        pdf.close()


def pdf_embedded_xml(content: bytes) -> bytes | None:
    """The XML invoice inside a Factur-X / ZUGFeRD PDF, if there is one."""
    try:
        attachments = PdfReader(io.BytesIO(content)).attachments
    except Exception as error:  # damaged or encrypted PDFs: just treat as a normal PDF
        log.info("could not read PDF attachments: %s", type(error).__name__)
        return None
    for name, files in attachments.items():
        if name.lower().endswith(".xml") and files:
            data = files[0]
            if b"CrossIndustryInvoice" in data[:4000] or b"Invoice" in data[:4000]:
                return data
    return None


def pdf_page_images(content: bytes, max_pages: int = MAX_AI_PAGES) -> list[bytes]:
    pdf = pdfium.PdfDocument(content)
    try:
        images = []
        for i in range(min(len(pdf), max_pages)):
            page = pdf[i]
            # Scale so the longer side lands near MAX_IMAGE_SIDE.
            width, height = page.get_size()
            scale = min(3.0, MAX_IMAGE_SIDE / max(width, height))
            pil = page.render(scale=scale).to_pil()
            images.append(_to_jpeg(pil))
            page.close()
        return images
    finally:
        pdf.close()


def prepare_image(content: bytes) -> bytes:
    """Upright, RGB, at most MAX_IMAGE_SIDE pixels, JPEG: the form the AI and OCR expect."""
    with Image.open(io.BytesIO(content)) as img:
        img.seek(0)  # first frame of GIF/TIFF
        upright = ImageOps.exif_transpose(img)
        return _to_jpeg(upright)


def _to_jpeg(img: Image.Image) -> bytes:
    if img.mode not in ("RGB", "L"):
        background = Image.new("RGB", img.size, "white")
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


class OCRUnavailable(RuntimeError):
    pass


def ocr_text(jpeg: bytes) -> str:
    """Reads printed text with Tesseract (Arabic, French, English). Used when the vision AI is unavailable."""
    try:
        import pytesseract

        with Image.open(io.BytesIO(jpeg)) as img:
            gray = ImageOps.grayscale(img)
            return pytesseract.image_to_string(gray, lang="ara+fra+eng", timeout=60)
    except (ImportError, EnvironmentError, RuntimeError) as error:
        raise OCRUnavailable(str(error)) from error
