import type { Doc, Source } from './types'

export function money(value: number | null | undefined, currency: string | null | undefined): string {
  if (value == null) return '—'
  if (currency && /^[A-Z]{3}$/.test(currency)) {
    try {
      return new Intl.NumberFormat('en-GB', { style: 'currency', currency, currencyDisplay: 'code' }).format(value)
    } catch {
      // unknown code: fall through
    }
  }
  return `${value.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${currency ? ` ${currency}` : ''}`
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export const SOURCE_LABEL: Record<Source, string> = {
  'e-invoice': 'E-invoice, read exactly',
  'pdf-text': 'PDF text, read by AI',
  vision: 'Image, read by AI',
  ocr: 'Image, read with OCR',
}

export const SOURCE_DETAIL: Record<Source, string> = {
  'e-invoice': 'Read exactly from the structured e-invoice data (XML), without AI.',
  'pdf-text': "Read from the PDF's text by AI.",
  vision: 'Read from the image by an AI that can see.',
  ocr: 'The image AI was unavailable, so the text was recognized (OCR) and then read by AI. Check the values.',
}

export function totalsByCurrency(docs: Doc[]): [string, number][] {
  const sums = new Map<string, number>()
  for (const doc of docs) {
    if (doc.state !== 'done' || doc.data?.total == null) continue
    const key = doc.data.currency ?? '—'
    const sign = doc.data.document_type === 'credit_note' ? -1 : 1
    sums.set(key, (sums.get(key) ?? 0) + sign * doc.data.total)
  }
  return [...sums.entries()].sort((a, b) => b[1] - a[1])
}
