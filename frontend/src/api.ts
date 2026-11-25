import type { ExtractResult, InvoiceData } from './types'

export interface AppConfig {
  maxFileMb: number
  googleDrive: boolean
}

export interface DriveFile {
  id: string
  name: string
  mimeType: string
  size: number | null
  resourceKey: string | null
}

export class ApiError extends Error {}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.error === 'string') return body.error
  } catch {
    // not JSON
  }
  return `The server answered with an error (${response.status}). Please try again.`
}

export async function getConfig(): Promise<AppConfig> {
  const response = await fetch('/api/config')
  if (!response.ok) return { maxFileMb: 10, googleDrive: false }
  return response.json()
}

export async function extractFile(file: Blob, filename: string, signal?: AbortSignal): Promise<ExtractResult> {
  const form = new FormData()
  form.append('file', file, filename)
  let response: Response
  try {
    response = await fetch('/api/extract', { method: 'POST', body: form, signal })
  } catch {
    throw new ApiError('Could not reach the server. Check your connection and try again.')
  }
  if (!response.ok) throw new ApiError(await errorMessage(response))
  return response.json()
}

export async function exportXlsx(rows: { filename: string; data: InvoiceData }[]): Promise<Blob> {
  const response = await fetch('/api/export/xlsx', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(rows),
  })
  if (!response.ok) throw new ApiError(await errorMessage(response))
  return response.blob()
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
  } catch {
    throw new ApiError('Could not reach the server. Check your connection and try again.')
  }
  if (!response.ok) throw new ApiError(await errorMessage(response))
  return response.json()
}

export const listDrive = (url: string) => postJson<{ files: DriveFile[]; skipped: number }>('/api/drive/list', { url })

export const extractDrive = (file: { id: string; name: string; mimeType: string; resourceKey: string | null }) =>
  postJson<ExtractResult>('/api/drive/extract', file)
