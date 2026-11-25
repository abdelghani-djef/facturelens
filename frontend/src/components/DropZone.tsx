import { useEffect, useRef, useState, type ReactNode } from 'react'
import { CameraIcon, UploadIcon } from './Icons'

const ACCEPT =
  '.pdf,.xml,.jpg,.jpeg,.png,.webp,.heic,.heif,.tif,.tiff,.gif,image/*,application/pdf,application/xml,text/xml'

interface Props {
  onFiles: (files: File[]) => void
  maxFileMb: number
  extraButton?: ReactNode
}

export function DropZone({ onFiles, maxFileMb, extraButton }: Props) {
  const [over, setOver] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const cameraInput = useRef<HTMLInputElement>(null)
  const [touch] = useState(() => typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches)

  // Paste a screenshot or copied file anywhere on the page.
  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const target = event.target as HTMLElement | null
      if (target?.closest('input, textarea')) return
      const pasted = [...(event.clipboardData?.files ?? [])]
      if (!pasted.length) return
      event.preventDefault()
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
      onFiles(
        pasted.map((f, i) =>
          f.name && f.name !== 'image.png' ? f : new File([f], `pasted-${stamp}${i ? `-${i}` : ''}.png`, { type: f.type }),
        ),
      )
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [onFiles])

  function take(list: FileList | null) {
    if (list?.length) onFiles([...list])
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false)
      }}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        take(e.dataTransfer.files)
      }}
      className={`rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
        over ? 'border-accent bg-accent-soft' : 'border-line bg-card'
      }`}
    >
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-accent-soft text-accent">
        <UploadIcon className="h-6 w-6" />
      </div>
      <p className="mt-4 text-lg font-semibold">Drop invoices and receipts here</p>
      <p className="mt-1 text-sm text-muted">
        {touch ? 'Or choose files, or take a photo.' : 'Or choose files, or paste a screenshot with Ctrl+V.'}
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent/90"
        >
          <UploadIcon className="h-4 w-4" /> Choose files
        </button>
        {touch ? (
          <button
            type="button"
            onClick={() => cameraInput.current?.click()}
            className="inline-flex items-center gap-2 rounded-lg border border-line bg-card px-4 py-2.5 text-sm font-semibold hover:border-ink"
          >
            <CameraIcon className="h-4 w-4" /> Take a photo
          </button>
        ) : null}
        {extraButton}
      </div>
      <p className="mt-5 text-xs text-muted">
        PDF, photos (JPG, PNG, HEIC), screenshots and e-invoices (XML, Factur-X){extraButton ? ', from your device or Google Drive' : ''} · up to {maxFileMb} MB each
      </p>
      <input
        ref={fileInput}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          take(e.target.files)
          e.target.value = ''
        }}
      />
      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          take(e.target.files)
          e.target.value = ''
        }}
      />
    </div>
  )
}
