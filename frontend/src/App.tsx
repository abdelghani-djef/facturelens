import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, exportXlsx, extractDrive, extractFile, getConfig, type AppConfig, type DriveFile } from './api'
import { isOk } from './checks'
import { DocList } from './components/DocList'
import { DocPanel } from './components/DocPanel'
import { DriveImport } from './components/DriveImport'
import { DropZone } from './components/DropZone'
import { LockIcon, LogoIcon } from './components/Icons'
import { download, toCsv } from './csv'
import { money, totalsByCurrency } from './format'
import { useDocs } from './store'
import type { Doc, InvoiceData } from './types'

const PARALLEL = 2

const FEATURES = [
  {
    title: 'Any source',
    body: 'PDFs, phone photos, screenshots and e-invoices (XML, Factur-X), in Arabic, French or English.',
  },
  {
    title: 'Totals checked',
    body: 'Line items, tax and total are added up. Anything that doesn’t match is marked for review.',
  },
  {
    title: 'Private',
    body: 'Files are deleted from the server as soon as they are read. Results stay in your browser.',
  },
]

export default function App() {
  const [docs, dispatch] = useDocs()
  const [config, setConfig] = useState<AppConfig>({ maxFileMb: 10, googleDrive: false })
  const [openId, setOpenId] = useState<string | null>(null)
  const [busy, setBusy] = useState<'xlsx' | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const files = useRef(new Map<string, File>()) // kept for this visit only, to read and retry
  const previews = useRef(new Map<string, string>())
  const started = useRef(new Set<string>())

  useEffect(() => {
    getConfig().then(setConfig).catch(() => undefined)
  }, [])

  const addFiles = useCallback(
    (list: File[]) => {
      const limit = config.maxFileMb * 1024 * 1024
      const added: Doc[] = list.map((file) => {
        const id = crypto.randomUUID()
        files.current.set(id, file)
        previews.current.set(id, URL.createObjectURL(file))
        const tooBig = file.size > limit
        return {
          id,
          filename: file.name || 'document',
          size: file.size,
          mime: file.type,
          addedAt: Date.now(),
          state: tooBig ? 'error' : 'queued',
          error: tooBig ? `Files must be ${config.maxFileMb} MB or smaller.` : undefined,
        }
      })
      dispatch({ type: 'add', docs: added })
    },
    [config.maxFileMb, dispatch],
  )

  const addDriveFiles = useCallback(
    (list: DriveFile[], skipped: number) => {
      const now = Date.now()
      dispatch({
        type: 'add',
        docs: list.map((file) => ({
          id: crypto.randomUUID(),
          filename: file.name,
          size: file.size ?? 0,
          mime: file.mimeType,
          addedAt: now,
          state: 'queued',
          drive: { id: file.id, mimeType: file.mimeType, resourceKey: file.resourceKey },
        })),
      })
      if (skipped) setNotice(`${skipped} file${skipped > 1 ? 's' : ''} in this folder ${skipped > 1 ? 'were' : 'was'} skipped (not a PDF, image or e-invoice, or over the 25-file limit).`)
    },
    [dispatch],
  )

  // Reads waiting files a few at a time: oldest drop first, and within a drop from the top of the list down.
  useEffect(() => {
    const reading = docs.filter((d) => d.state === 'reading').length
    const waiting = docs
      .filter((d) => d.state === 'queued' && (files.current.has(d.id) || d.drive) && !started.current.has(d.id))
      .sort((a, b) => a.addedAt - b.addedAt)
    for (const doc of waiting.slice(0, Math.max(0, PARALLEL - reading))) {
      started.current.add(doc.id)
      dispatch({ type: 'start', id: doc.id })
      const file = files.current.get(doc.id)
      const read = file
        ? extractFile(file, doc.filename)
        : extractDrive({ id: doc.drive!.id, name: doc.filename, mimeType: doc.drive!.mimeType, resourceKey: doc.drive!.resourceKey })
      read
        .then((result) => dispatch({ type: 'done', id: doc.id, result }))
        .catch((error) =>
          dispatch({ type: 'fail', id: doc.id, error: error instanceof ApiError ? error.message : 'Something went wrong.' }),
        )
        .finally(() => started.current.delete(doc.id))
    }
  }, [docs, dispatch])

  const retry = (id: string) => {
    if (files.current.has(id) || docs.find((d) => d.id === id)?.drive) dispatch({ type: 'retry', id })
    else setNotice('This file is no longer in memory. Add it again to read it.')
  }

  const remove = (id: string) => {
    const url = previews.current.get(id)
    if (url) URL.revokeObjectURL(url)
    previews.current.delete(id)
    files.current.delete(id)
    dispatch({ type: 'remove', id })
    setOpenId(null)
  }

  const clearAll = () => {
    if (!window.confirm('Remove all documents from this page? This cannot be undone.')) return
    previews.current.forEach((url) => URL.revokeObjectURL(url))
    previews.current.clear()
    files.current.clear()
    dispatch({ type: 'clear' })
  }

  const done = docs.filter((d): d is Doc & { data: InvoiceData } => d.state === 'done' && !!d.data)
  const review = done.filter((d) => !isOk(d.checks)).length
  const open = done.find((d) => d.id === openId)

  async function exportExcel() {
    setBusy('xlsx')
    try {
      const blob = await exportXlsx(done.map((d) => ({ filename: d.filename, data: d.data })))
      download(blob, 'facturelens-export.xlsx')
    } catch (error) {
      setNotice(error instanceof ApiError ? error.message : 'The export failed. Please try again.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <a href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-white">
              <LogoIcon className="h-5 w-5" />
            </span>
            FactureLens
          </a>
          <a
            href="https://github.com/abdelghani-djef/facturelens"
            target="_blank"
            rel="noopener"
            className="text-sm text-muted hover:text-ink"
          >
            Source on GitHub ↗
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
        <section className="py-10 sm:py-14">
          <h1 className="max-w-2xl text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
            Turn invoices and receipts into clean, checked data.
          </h1>
          <p className="mt-3 max-w-2xl text-muted">
            Drop PDFs, photos, screenshots or e-invoices. FactureLens reads them, checks the totals, and exports
            everything to Excel.
          </p>
          <p className="mt-4 inline-flex items-center gap-2 rounded-full bg-card px-3 py-1.5 text-xs text-muted ring-1 ring-line">
            <LockIcon className="h-3.5 w-3.5" /> Files are deleted after reading. Results stay in your browser.
          </p>
        </section>

        <DropZone
          onFiles={addFiles}
          maxFileMb={config.maxFileMb}
          extraButton={config.googleDrive ? <DriveImport onImport={addDriveFiles} /> : null}
        />

        {notice ? (
          <div className="mt-4 flex items-start justify-between gap-3 rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
            <span>{notice}</span>
            <button type="button" className="font-semibold" onClick={() => setNotice(null)}>
              OK
            </button>
          </div>
        ) : null}

        {docs.length ? (
          <section className="mt-10">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold tracking-tight">
                  {docs.length} document{docs.length > 1 ? 's' : ''}
                </h2>
                <p className="mt-1 text-sm text-muted">
                  {review ? `${review} need${review > 1 ? '' : 's'} review · ` : ''}
                  {totalsByCurrency(docs)
                    .map(([currency, sum]) => money(sum, currency === '—' ? null : currency))
                    .join(' · ') || 'Reading…'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={!done.length || busy !== null}
                  onClick={exportExcel}
                  className="rounded-lg bg-ink px-3.5 py-2 text-sm font-semibold text-white hover:bg-ink/85 disabled:opacity-40"
                >
                  {busy === 'xlsx' ? 'Exporting…' : 'Export Excel'}
                </button>
                <button
                  type="button"
                  disabled={!done.length}
                  onClick={() => download(toCsv(done), 'facturelens-export.csv')}
                  className="rounded-lg border border-line bg-card px-3.5 py-2 text-sm font-semibold hover:border-ink disabled:opacity-40"
                >
                  Export CSV
                </button>
                <button
                  type="button"
                  onClick={clearAll}
                  className="rounded-lg px-3 py-2 text-sm font-medium text-muted hover:bg-card hover:text-bad"
                >
                  Clear all
                </button>
              </div>
            </div>
            <div className="mt-4">
              <DocList docs={docs} onOpen={setOpenId} onRetry={retry} />
            </div>
            <p className="mt-3 text-xs text-muted">Click a document to see its details, fix a value, or check why it needs review.</p>
          </section>
        ) : (
          <section className="mt-12 grid gap-4 sm:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-xl border border-line bg-card p-5">
                <p className="font-semibold">{f.title}</p>
                <p className="mt-1 text-sm text-muted">{f.body}</p>
              </div>
            ))}
          </section>
        )}
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-5xl flex-col gap-1 px-4 py-6 text-sm text-muted sm:flex-row sm:justify-between sm:px-6">
          <span>FactureLens · FastAPI, React and Groq AI</span>
          <a href="https://abdelghani-djef.github.io/#contact" className="text-accent hover:underline">
            Built by Abdelghani Djef — get in touch
          </a>
        </div>
      </footer>

      {open ? (
        <DocPanel
          doc={open}
          previewUrl={previews.current.get(open.id)}
          onClose={() => setOpenId(null)}
          onEdit={(data) => dispatch({ type: 'edit', id: open.id, data })}
          onRemove={() => remove(open.id)}
        />
      ) : null}
    </div>
  )
}
