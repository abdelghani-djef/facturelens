import { useEffect, useReducer } from 'react'
import { runChecks } from './checks'
import type { Doc, ExtractResult, InvoiceData } from './types'

// Results live only in this browser (localStorage); files are never stored.
const STORAGE_KEY = 'facturelens.docs.v1'

export type Action =
  | { type: 'add'; docs: Doc[] }
  | { type: 'start'; id: string }
  | { type: 'done'; id: string; result: ExtractResult }
  | { type: 'fail'; id: string; error: string }
  | { type: 'retry'; id: string }
  | { type: 'edit'; id: string; data: InvoiceData }
  | { type: 'remove'; id: string }
  | { type: 'clear' }

function reducer(docs: Doc[], action: Action): Doc[] {
  const patch = (id: string, change: Partial<Doc>) => docs.map((d) => (d.id === id ? { ...d, ...change } : d))
  switch (action.type) {
    case 'add':
      return [...action.docs, ...docs]
    case 'start':
      return patch(action.id, { state: 'reading', error: undefined })
    case 'done':
      return patch(action.id, {
        state: 'done',
        source: action.result.source,
        model: action.result.model,
        warnings: action.result.warnings,
        data: action.result.data,
        checks: action.result.checks,
      })
    case 'fail':
      return patch(action.id, { state: 'error', error: action.error })
    case 'retry':
      return patch(action.id, { state: 'queued', error: undefined })
    case 'edit':
      return patch(action.id, { data: action.data, checks: runChecks(action.data), edited: true })
    case 'remove':
      return docs.filter((d) => d.id !== action.id)
    case 'clear':
      return []
  }
}

function load(): Doc[] {
  try {
    const saved: Doc[] = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    // Uploaded files are not kept across visits, so unfinished ones can't resume; Drive ones can.
    return saved.map((d) =>
      d.state === 'queued' || d.state === 'reading'
        ? d.drive
          ? { ...d, state: 'queued' }
          : { ...d, state: 'error', error: 'Interrupted. Add the file again to read it.' }
        : d,
    )
  } catch {
    return []
  }
}

export function useDocs() {
  const [docs, dispatch] = useReducer(reducer, undefined, load)
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(docs))
    } catch {
      // storage full or blocked: results still work for this visit
    }
  }, [docs])
  return [docs, dispatch] as const
}
