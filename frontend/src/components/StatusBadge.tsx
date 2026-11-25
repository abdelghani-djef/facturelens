import { isOk } from '../checks'
import type { Doc } from '../types'
import { AlertIcon, CheckIcon, Spinner } from './Icons'

export function StatusBadge({ doc }: { doc: Doc }) {
  const base = 'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold'
  switch (doc.state) {
    case 'queued':
      return <span className={`${base} bg-paper text-muted`}>Waiting</span>
    case 'reading':
      return (
        <span className={`${base} bg-accent-soft text-accent`}>
          <Spinner /> Reading…
        </span>
      )
    case 'error':
      return (
        <span className={`${base} bg-bad-soft text-bad`}>
          <AlertIcon className="h-3.5 w-3.5" /> Failed
        </span>
      )
    case 'done':
      return isOk(doc.checks) ? (
        <span className={`${base} bg-ok-soft text-ok`}>
          <CheckIcon className="h-3.5 w-3.5" /> Checked
        </span>
      ) : (
        <span className={`${base} bg-warn-soft text-warn`}>
          <AlertIcon className="h-3.5 w-3.5" /> Needs review
        </span>
      )
  }
}
