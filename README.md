# FactureLens

**Turns invoices and receipts into clean, checked data.** Drop PDFs, phone photos, screenshots, e-invoices or a Google Drive folder link. FactureLens reads each document in Arabic, French or English, checks that the numbers add up, and exports everything to Excel.

**Live demo: [facturelens.35-180-91-97.sslip.io](https://facturelens.35-180-91-97.sslip.io)**

## What it reads

| Source | How | Accuracy |
| --- | --- | --- |
| E-invoices: UBL XML, CII XML, Factur-X / ZUGFeRD PDFs | Parsed directly from the structured data, no AI | Exact |
| PDFs with a text layer | Text extracted, then an AI fills a strict JSON schema | Very high |
| Photos, screenshots, scanned PDFs | A vision model reads the image; if it is unavailable, Tesseract OCR (Arabic, French, English) feeds a text model | High |
| Google Drive file or folder links | Files shared as "Anyone with the link" are listed and read like uploads; Google Docs are exported to PDF first | As above |

Every document then goes through the same checks:

- a total and a valid date are present;
- each line's quantity × unit price equals its amount;
- the lines add up to the subtotal or the total;
- subtotal + tax equals the total.

A document that fails any check is marked **Needs review**. Every field can be corrected in the browser, and the checks run again on each change.

## Privacy

Files are read in memory and dropped as soon as the result is sent back; nothing is written to disk on the server. Results are kept only in the visitor's own browser (localStorage). The AI provider receives the document and a hash of the visitor's IP address, never the address itself.

## Tech stack

| Part | Choice |
| --- | --- |
| Backend | Python 3.13, FastAPI, pypdfium2 and pypdf (PDF text, rendering, Factur-X attachments), Pillow with HEIC support, defusedxml, Tesseract OCR, openpyxl |
| AI | Groq API: `qwen/qwen3.8-27b` for images, `openai/gpt-oss-120b` for text, with automatic fallback between models and waiting out short rate limits |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4 |
| Deploy | One Docker image (the API serves the built frontend), behind Caddy for HTTPS |
| Tests | 41 pytest tests, with Groq and Google Drive replaced by stand-ins |

## Run it locally

Needs [uv](https://docs.astral.sh/uv/) and Node.js 22 or newer.

```bash
# API on port 8000
cd backend
echo "GROQ_API_KEY=your-key" > .env        # free key at console.groq.com
set -a && . ./.env && set +a
uv run uvicorn app.main:app --reload

# Frontend on port 5173, in another terminal (proxies /api to port 8000)
cd frontend
npm install
npm run dev
```

Tesseract is only needed for the OCR fallback (`tesseract-ocr` with the `ara` and `fra` languages); the Docker image includes it.

Run the tests with `cd backend && uv run pytest`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | none | Required. Groq API key. |
| `GOOGLE_API_KEY` | none | Turns on Google Drive link import. A Google Cloud API key restricted to the Drive API. |
| `MAX_PARALLEL` | `2` | Documents processed at the same time. |
| `DAILY_FILE_LIMIT` | `400` | Files accepted per day across the site, to protect the AI quota. Each visitor is also limited to 30 files per 10 minutes. |

### Google Drive import

1. In the [Google Cloud console](https://console.cloud.google.com/), create a project and enable the **Google Drive API**.
2. Under **APIs & Services → Credentials**, create an **API key**. Restrict it to the Google Drive API.
3. Set it as `GOOGLE_API_KEY` and restart. A **Google Drive link** button appears next to **Choose files**.

## Deploy

```bash
docker build -t facturelens:latest .
docker run -p 8000:8000 -e GROQ_API_KEY=your-key facturelens:latest
```

The live demo runs on a 512 MB VPS behind a shared Caddy gateway: the image is built on a workstation and loaded on the server with `docker save | ssh … docker load`, using [deploy/compose.vps.yml](deploy/compose.vps.yml).

## Project structure

```
backend/app/
  main.py               API: upload, Drive import, Excel export, config
  drive.py              Google Drive links: listing and downloading with an API key
  export.py             Excel export
  ratelimit.py          per-visitor and daily limits
  extract/
    pipeline.py         chooses the reader for each file and falls back when needed
    einvoice.py         UBL and CII (Factur-X) parsing, no AI
    files.py            file type detection, PDF text and rendering, image preparation, OCR
    groq.py             AI calls with model fallback and rate-limit waits
    prompt.py           extraction rules given to the AI
    schema.py           the document format shared by every reader
    validate.py         cleaning and arithmetic checks
backend/tests/          pytest suite
frontend/src/
  App.tsx               page, processing queue, exports
  components/           drop zone, Drive import, document list, review panel
  checks.ts             the same checks, re-run in the browser after edits
  store.ts              results kept in the browser
```
