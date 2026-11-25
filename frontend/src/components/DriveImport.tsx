import { useEffect, useRef, useState } from 'react'
import { ApiError, listDrive, type DriveFile } from '../api'
import { CloseIcon, DriveIcon, Spinner } from './Icons'

interface Props {
  onImport: (files: DriveFile[], skipped: number) => void
}

export function DriveImport({ onImport }: Props) {
  const [open, setOpen] = useState(false)
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const field = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    field.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const { files, skipped } = await listDrive(url)
      onImport(files, skipped)
      setUrl('')
      setOpen(false)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-lg border border-line bg-card px-4 py-2.5 text-sm font-semibold hover:border-ink"
      >
        <DriveIcon className="h-4 w-4" /> Google Drive link
      </button>

      {open ? (
        <div className="fixed inset-0 z-40 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label="Import from Google Drive">
          <button type="button" aria-label="Close" className="absolute inset-0 bg-ink/30" onClick={() => setOpen(false)} />
          <form onSubmit={submit} className="relative w-full max-w-lg rounded-2xl bg-card p-6 text-left shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Import from Google Drive</h2>
                <p className="mt-1 text-sm text-muted">
                  Paste a link to a file or a whole folder. In Drive, share it as <b>Anyone with the link</b> first.
                </p>
              </div>
              <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-1.5 hover:bg-paper" aria-label="Close">
                <CloseIcon className="h-5 w-5" />
              </button>
            </div>
            <input
              ref={field}
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://drive.google.com/drive/folders/…"
              className="mt-4 w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm outline-none focus:border-accent focus:bg-card focus:ring-2 focus:ring-accent/15"
            />
            {error ? <p className="mt-2 text-sm text-bad">{error}</p> : null}
            <p className="mt-3 text-xs text-muted">Up to 25 PDFs, photos, e-invoices or Google Docs per folder are read.</p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} className="rounded-lg px-4 py-2 text-sm font-medium text-muted hover:bg-paper">
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-accent/90 disabled:opacity-60"
              >
                {loading ? <Spinner /> : null} {loading ? 'Opening…' : 'Import'}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </>
  )
}
