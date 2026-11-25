// Mirrors backend/app/extract/schema.py.

export type DocumentType = 'invoice' | 'receipt' | 'credit_note' | 'other'
export type Source = 'e-invoice' | 'pdf-text' | 'vision' | 'ocr'

export interface Party {
  name: string | null
  tax_id: string | null
  address: string | null
}

export interface LineItem {
  description: string
  quantity: number | null
  unit_price: number | null
  amount: number | null
}

export interface InvoiceData {
  document_type: DocumentType
  vendor: Party
  customer: Party
  invoice_number: string | null
  issue_date: string | null
  due_date: string | null
  currency: string | null
  line_items: LineItem[]
  subtotal: number | null
  tax_amount: number | null
  tax_rate: number | null
  total: number | null
  payment_method: string | null
  language: string | null
}

export interface Check {
  id: string
  ok: boolean
  message: string
}

export interface ExtractResult {
  filename: string
  source: Source
  model: string | null
  data: InvoiceData
  checks: Check[]
  status: 'ok' | 'review'
  pages: number
  warnings: string[]
}

export type DocState = 'queued' | 'reading' | 'done' | 'error'

export interface Doc {
  id: string
  filename: string
  size: number
  mime: string
  addedAt: number
  state: DocState
  error?: string
  source?: Source
  model?: string | null
  warnings?: string[]
  data?: InvoiceData
  checks?: Check[]
  edited?: boolean
  // Set for documents imported from a Google Drive link; they can be re-read without the file.
  drive?: { id: string; mimeType: string; resourceKey: string | null }
}
