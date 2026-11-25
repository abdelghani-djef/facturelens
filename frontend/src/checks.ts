// Same checks as backend/app/extract/validate.py, re-run in the browser after the user edits a value.
import type { Check, InvoiceData } from './types'

const close = (a: number, b: number, reference?: number) => {
  const scale = Math.abs(reference ?? Math.max(Math.abs(a), Math.abs(b)))
  return Math.abs(a - b) <= Math.max(0.02, scale * 0.005)
}

const fmt = (value: number) =>
  value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).replaceAll(',', ' ')

function validDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const day = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(day.getTime()) || day.toISOString().slice(0, 10) !== value) return false
  const nextYear = new Date()
  nextYear.setFullYear(nextYear.getFullYear() + 1)
  return day >= new Date('2000-01-01T00:00:00Z') && day <= nextYear
}

export function runChecks(data: InvoiceData): Check[] {
  const checks: Check[] = []

  checks.push(
    data.total == null
      ? { id: 'total', ok: false, message: 'No total found.' }
      : { id: 'total', ok: true, message: `Total found: ${fmt(data.total)}.` },
  )

  if (data.issue_date) {
    const ok = validDate(data.issue_date)
    checks.push({ id: 'date', ok, message: ok ? 'Date looks valid.' : `Date ${data.issue_date} looks wrong.` })
  } else {
    checks.push({ id: 'date', ok: false, message: 'No date found.' })
  }

  const badLines = data.line_items
    .map((item, i) => ({ item, label: item.description || `line ${i + 1}` }))
    .filter(
      ({ item }) =>
        item.quantity != null &&
        item.unit_price != null &&
        item.amount != null &&
        !close(item.quantity * item.unit_price, item.amount),
    )
    .map(({ label }) => label)
  if (badLines.length) {
    checks.push({
      id: 'line_math',
      ok: false,
      message: `Quantity × unit price doesn't match the amount on: ${badLines.slice(0, 3).join(', ')}.`,
    })
  }

  const amounts = data.line_items.map((item) => item.amount).filter((a): a is number => a != null)
  if (amounts.length && amounts.length === data.line_items.length) {
    const sum = amounts.reduce((a, b) => a + b, 0)
    const targets = [data.subtotal, data.total].filter((t): t is number => t != null)
    if (targets.length) {
      const ok = targets.some((t) => close(sum, t))
      checks.push({
        id: 'lines_sum',
        ok,
        message: ok
          ? `Line items add up to ${fmt(sum)}.`
          : `Line items add up to ${fmt(sum)}, which matches neither the subtotal nor the total.`,
      })
    }
  }

  if (data.subtotal != null && data.tax_amount != null && data.total != null) {
    const expected = data.subtotal + data.tax_amount
    const ok = close(expected, data.total, data.total)
    checks.push({
      id: 'tax_math',
      ok,
      message: ok ? 'Subtotal + tax = total.' : `Subtotal + tax = ${fmt(expected)}, but the total is ${fmt(data.total)}.`,
    })
  }

  return checks
}

export const isOk = (checks: Check[] | undefined) => !!checks && checks.every((check) => check.ok)
