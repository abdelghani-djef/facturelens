import type { Doc } from './types'

const COLUMNS: [string, (doc: Doc) => unknown][] = [
  ['File', (d) => d.filename],
  ['Type', (d) => d.data?.document_type],
  ['Vendor', (d) => d.data?.vendor.name],
  ['Vendor tax ID', (d) => d.data?.vendor.tax_id],
  ['Customer', (d) => d.data?.customer.name],
  ['Number', (d) => d.data?.invoice_number],
  ['Date', (d) => d.data?.issue_date],
  ['Due date', (d) => d.data?.due_date],
  ['Currency', (d) => d.data?.currency],
  ['Subtotal', (d) => d.data?.subtotal],
  ['Tax', (d) => d.data?.tax_amount],
  ['Tax rate %', (d) => d.data?.tax_rate],
  ['Total', (d) => d.data?.total],
  ['Payment', (d) => d.data?.payment_method],
  ['Checks', (d) => (d.checks?.every((c) => c.ok) ? 'ok' : 'needs review')],
]

function cell(value: unknown): string {
  if (value == null) return ''
  const text = String(value)
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

export function toCsv(docs: Doc[]): Blob {
  const rows = [COLUMNS.map(([name]) => name), ...docs.map((doc) => COLUMNS.map(([, get]) => cell(get(doc))))]
  // The byte-order mark makes Excel open UTF-8 (Arabic, accents) correctly.
  return new Blob(['﻿' + rows.map((r) => r.join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' })
}

export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
