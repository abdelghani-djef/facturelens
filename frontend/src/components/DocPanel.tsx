import { useEffect, useState } from 'react'
import { SOURCE_DETAIL } from '../format'
import type { Doc, DocumentType, InvoiceData, LineItem, Party } from '../types'
import { AlertIcon, CheckIcon, CloseIcon, TrashIcon } from './Icons'
import { StatusBadge } from './StatusBadge'

interface Props {
  doc: Doc & { data: InvoiceData }
  previewUrl?: string
  onClose: () => void
  onEdit: (data: InvoiceData) => void
  onRemove: () => void
}

const input =
  'mt-1 w-full rounded-lg border border-line bg-paper px-2.5 py-1.5 text-sm outline-none focus:border-accent focus:bg-card focus:ring-2 focus:ring-accent/15'

const toNumber = (value: string) => {
  const n = parseFloat(value.replace(',', '.'))
  return value.trim() === '' || Number.isNaN(n) ? null : n
}

function TextField({ label, value, onChange, type = 'text' }: {
  label: string
  value: string | null
  onChange: (v: string | null) => void
  type?: string
}) {
  return (
    <label className="block text-xs font-medium text-muted">
      {label}
      <input
        type={type}
        className={`${input} text-ink`}
        value={value ?? ''}
        dir="auto"
        onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
      />
    </label>
  )
}

// Saves on every keystroke, so closing the panel never loses an edit. Keeps what the user typed
// ("12." on the way to "12.5") as long as it still means the saved number.
function NumberInput({ value, onChange, className, label }: {
  value: number | null
  onChange: (v: number | null) => void
  className: string
  label?: string
}) {
  const [text, setText] = useState(value == null ? '' : String(value))
  useEffect(() => {
    setText((current) => (toNumber(current) === value ? current : value == null ? '' : String(value)))
  }, [value])
  return (
    <input
      inputMode="decimal"
      aria-label={label}
      className={className}
      value={text}
      onChange={(e) => {
        const next = e.target.value
        setText(next)
        const number = toNumber(next)
        if (number !== null || next.trim() === '') onChange(number)
      }}
    />
  )
}

function NumberField({ label, value, onChange }: { label: string; value: number | null; onChange: (v: number | null) => void }) {
  return (
    <label className="block text-xs font-medium text-muted">
      {label}
      <NumberInput value={value} onChange={onChange} className={`${input} text-right text-ink tabular-nums`} />
    </label>
  )
}

export function DocPanel({ doc, previewUrl, onClose, onEdit, onRemove }: Props) {
  const data = doc.data
  const set = (change: Partial<InvoiceData>) => onEdit({ ...data, ...change })
  const setParty = (key: 'vendor' | 'customer', change: Partial<Party>) => set({ [key]: { ...data[key], ...change } })
  const setLine = (i: number, change: Partial<LineItem>) =>
    set({ line_items: data.line_items.map((item, j) => (j === i ? { ...item, ...change } : item)) })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const isPdf = doc.mime === 'application/pdf' || doc.filename.toLowerCase().endsWith('.pdf')
  const isImage = doc.mime.startsWith('image/') && !/hei[cf]/i.test(doc.mime)

  return (
    <div className="fixed inset-0 z-30 flex justify-end" role="dialog" aria-modal="true" aria-label={`Details of ${doc.filename}`}>
      <button type="button" aria-label="Close" className="absolute inset-0 bg-ink/30" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-2xl flex-col overflow-hidden bg-card shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <p className="truncate font-semibold" dir="auto">{doc.filename}</p>
            <div className="mt-1.5"><StatusBadge doc={doc} /></div>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 hover:bg-paper" aria-label="Close details">
            <CloseIcon className="h-5 w-5" />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          {previewUrl && (isPdf || isImage) ? (
            <div className="overflow-hidden rounded-xl border border-line bg-paper">
              {isPdf ? (
                <iframe src={previewUrl} title="Document preview" className="h-80 w-full" />
              ) : (
                <img src={previewUrl} alt="The uploaded document" className="max-h-80 w-full object-contain" />
              )}
            </div>
          ) : null}

          <section>
            <ul className="space-y-1.5">
              {doc.checks?.map((check) => (
                <li key={check.id} className={`flex items-start gap-2 text-sm ${check.ok ? 'text-ok' : 'text-warn'}`}>
                  {check.ok ? <CheckIcon className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />}
                  <span>{check.message}</span>
                </li>
              ))}
            </ul>
            {doc.warnings?.map((w) => (
              <p key={w} className="mt-2 rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">{w}</p>
            ))}
            {doc.source ? (
              <p className="mt-3 text-xs text-muted">
                {SOURCE_DETAIL[doc.source]}
                {doc.model ? ` Model: ${doc.model}.` : ''}
              </p>
            ) : null}
          </section>

          <section className="grid gap-3 sm:grid-cols-2">
            <TextField label="Vendor" value={data.vendor.name} onChange={(v) => setParty('vendor', { name: v })} />
            <TextField label="Vendor tax ID" value={data.vendor.tax_id} onChange={(v) => setParty('vendor', { tax_id: v })} />
            <TextField label="Customer" value={data.customer.name} onChange={(v) => setParty('customer', { name: v })} />
            <TextField label="Number" value={data.invoice_number} onChange={(v) => set({ invoice_number: v })} />
            <TextField label="Date" type="date" value={data.issue_date} onChange={(v) => set({ issue_date: v })} />
            <TextField label="Due date" type="date" value={data.due_date} onChange={(v) => set({ due_date: v })} />
            <label className="block text-xs font-medium text-muted">
              Type
              <select
                className={`${input} text-ink`}
                value={data.document_type}
                onChange={(e) => set({ document_type: e.target.value as DocumentType })}
              >
                <option value="invoice">Invoice</option>
                <option value="receipt">Receipt</option>
                <option value="credit_note">Credit note</option>
                <option value="other">Other</option>
              </select>
            </label>
            <TextField label="Currency" value={data.currency} onChange={(v) => set({ currency: v?.toUpperCase().slice(0, 3) ?? null })} />
            <NumberField label="Subtotal (before tax)" value={data.subtotal} onChange={(v) => set({ subtotal: v })} />
            <NumberField label="Tax" value={data.tax_amount} onChange={(v) => set({ tax_amount: v })} />
            <NumberField label="Tax rate %" value={data.tax_rate} onChange={(v) => set({ tax_rate: v })} />
            <NumberField label="Total" value={data.total} onChange={(v) => set({ total: v })} />
            <TextField label="Payment method" value={data.payment_method} onChange={(v) => set({ payment_method: v })} />
          </section>

          <section>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Line items</h3>
              <button
                type="button"
                onClick={() => set({ line_items: [...data.line_items, { description: '', quantity: null, unit_price: null, amount: null }] })}
                className="rounded-md px-2 py-1 text-xs font-semibold text-accent hover:bg-accent-soft"
              >
                Add line
              </button>
            </div>
            {data.line_items.length ? (
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[480px] text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted">
                      <th className="pb-1 font-medium">Description</th>
                      <th className="w-16 pb-1 text-right font-medium">Qty</th>
                      <th className="w-24 pb-1 text-right font-medium">Unit price</th>
                      <th className="w-24 pb-1 text-right font-medium">Amount</th>
                      <th className="w-8" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.line_items.map((item, i) => (
                      <tr key={i} className="align-top">
                        <td className="pr-2 pb-2">
                          <input className={`${input} mt-0`} dir="auto" value={item.description}
                            onChange={(e) => setLine(i, { description: e.target.value })} />
                        </td>
                        {(['quantity', 'unit_price', 'amount'] as const).map((key) => (
                          <td key={key} className="pr-2 pb-2">
                            <NumberInput value={item[key]} onChange={(v) => setLine(i, { [key]: v })}
                              label={`${key.replace('_', ' ')}, line ${i + 1}`}
                              className={`${input} mt-0 text-right tabular-nums`} />
                          </td>
                        ))}
                        <td className="pb-2">
                          <button type="button" aria-label="Remove line" className="mt-1 rounded p-1 text-muted hover:text-bad"
                            onClick={() => set({ line_items: data.line_items.filter((_, j) => j !== i) })}>
                            <TrashIcon className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted">No line items on this document.</p>
            )}
          </section>
        </div>

        <footer className="flex items-center justify-between border-t border-line px-5 py-3">
          <button type="button" onClick={onRemove}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-bad hover:bg-bad-soft">
            <TrashIcon className="h-4 w-4" /> Remove
          </button>
          <button type="button" onClick={onClose} className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-ink/85">
            Done
          </button>
        </footer>
      </div>
    </div>
  )
}
