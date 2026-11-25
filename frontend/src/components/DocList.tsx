import { money, SOURCE_LABEL } from '../format'
import type { Doc } from '../types'
import { StatusBadge } from './StatusBadge'

interface Props {
  docs: Doc[]
  onOpen: (id: string) => void
  onRetry: (id: string) => void
}

function Secondary({ doc }: { doc: Doc }) {
  if (doc.state === 'error') return <span className="text-bad">{doc.error}</span>
  if (doc.state !== 'done') return <span className="text-muted">{doc.state === 'reading' ? 'Reading the document…' : 'In line'}</span>
  return (
    <span className="text-muted">
      {doc.source ? SOURCE_LABEL[doc.source] : null}
      {doc.edited ? ' · edited' : null}
    </span>
  )
}

export function DocList({ docs, onOpen, onRetry }: Props) {
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-card">
      {docs.map((doc) => {
        const clickable = doc.state === 'done'
        return (
          <li key={doc.id}>
            <div
              role={clickable ? 'button' : undefined}
              tabIndex={clickable ? 0 : undefined}
              onClick={clickable ? () => onOpen(doc.id) : undefined}
              onKeyDown={clickable ? (e) => (e.key === 'Enter' || e.key === ' ') && onOpen(doc.id) : undefined}
              className={`grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-4 py-3.5 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto_auto] ${
                clickable ? 'cursor-pointer hover:bg-paper' : ''
              }`}
            >
              <div className="min-w-0">
                <p className="truncate font-medium" dir="auto">
                  {doc.data?.vendor.name || doc.filename}
                </p>
                <p className="truncate text-xs">
                  {doc.data?.vendor.name ? <span className="text-muted">{doc.filename} · </span> : null}
                  <Secondary doc={doc} />
                </p>
              </div>
              <div className="hidden min-w-0 text-sm text-muted sm:block">
                {doc.data?.issue_date ?? ''}
                {doc.data?.invoice_number ? <span className="block truncate text-xs">N° {doc.data.invoice_number}</span> : null}
              </div>
              <div className="text-right font-semibold tabular-nums sm:min-w-32">
                {doc.state === 'done' ? money(doc.data?.total, doc.data?.currency) : ''}
              </div>
              <div className="col-span-2 flex items-center gap-2 sm:col-span-1 sm:justify-end">
                <StatusBadge doc={doc} />
                {doc.state === 'error' ? (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      onRetry(doc.id)
                    }}
                    className="rounded-md px-2 py-1 text-xs font-semibold text-accent hover:bg-accent-soft"
                  >
                    Try again
                  </button>
                ) : null}
              </div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
