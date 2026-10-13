import type { Clip, ClipEditorSettings, HealthResponse, Project, ProjectSettings, Stats } from './types'
import { normalizeClip, normalizeProject, normalizeStats } from './utils'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

class ApiError extends Error {
  status: number
  details?: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

function endpoint(path: string): string {
  return `${API_BASE}${path}`
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) return response.json()
  const text = await response.text()
  return text ? { message: text } : null
}

function apiErrorMessage(body: unknown, status: number): string {
  const details = (body && typeof body === 'object' ? body : {}) as Record<string, unknown>
  if (typeof details.detail === 'string' && details.detail) return details.detail
  if (Array.isArray(details.detail)) {
    const messages = details.detail
      .map((item) => item && typeof item === 'object' ? String((item as Record<string, unknown>).msg ?? '') : '')
      .filter(Boolean)
    if (messages.length) return messages.join(' · ')
  }
  if (typeof details.message === 'string' && details.message) return details.message
  return `İstek tamamlanamadı (${status})`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(endpoint(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body instanceof FormData ? {} : init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  const body = await parseResponse(response)
  if (!response.ok) {
    throw new ApiError(apiErrorMessage(body, response.status), response.status, body)
  }
  return body as T
}

function unwrapProject(raw: unknown): Project {
  const record = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return normalizeProject(record.project ?? record.data ?? raw)
}

export async function getHealth(): Promise<HealthResponse> {
  const raw = await request<unknown>('/api/health')
  const record = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return (record.health ?? record) as HealthResponse
}

export async function getStats(): Promise<Stats> {
  const raw = await request<unknown>('/api/stats')
  const record = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return normalizeStats(record.stats ?? record.data ?? raw)
}

export async function getProjects(): Promise<Project[]> {
  const raw = await request<unknown>('/api/projects')
  const record = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const list = Array.isArray(raw)
    ? raw
    : Array.isArray(record.projects)
      ? record.projects
      : Array.isArray(record.items)
        ? record.items
        : Array.isArray(record.data)
          ? record.data
          : []
  return list.map(normalizeProject)
}

export async function getProject(projectId: string): Promise<Project> {
  return unwrapProject(await request<unknown>(`/api/projects/${encodeURIComponent(projectId)}`))
}

export function createProject(
  file: File,
  settings: ProjectSettings,
  onProgress?: (progress: number) => void,
): Promise<Project> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)
    form.append('settings', JSON.stringify(settings))

    const xhr = new XMLHttpRequest()
    xhr.open('POST', endpoint('/api/projects'))
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100))
    })
    xhr.addEventListener('load', () => {
      let body: unknown = null
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null
      } catch {
        body = { message: xhr.responseText }
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100)
        resolve(unwrapProject(body))
      } else {
        reject(new ApiError(apiErrorMessage(body, xhr.status), xhr.status, body))
      }
    })
    xhr.addEventListener('error', () => reject(new ApiError('Yerel sunucuya ulaşılamadı.', 0)))
    xhr.addEventListener('abort', () => reject(new ApiError('Yükleme iptal edildi.', 0)))
    xhr.send(form)
  })
}

export async function retryProject(projectId: string): Promise<Project> {
  return unwrapProject(
    await request<unknown>(`/api/projects/${encodeURIComponent(projectId)}/retry`, { method: 'POST' }),
  )
}

export async function deleteProject(projectId: string): Promise<void> {
  await request<unknown>(`/api/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' })
}

export async function updateClip(
  projectId: string,
  clipId: string,
  settings: ClipEditorSettings,
): Promise<Clip> {
  const raw = await request<unknown>(
    `/api/projects/${encodeURIComponent(projectId)}/clips/${encodeURIComponent(clipId)}`,
    { method: 'PATCH', body: JSON.stringify(settings) },
  )
  const record = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return normalizeClip(record.clip ?? record.data ?? raw, projectId)
}

export async function renderClip(projectId: string, clipId: string): Promise<Clip> {
  const raw = await request<unknown>(
    `/api/projects/${encodeURIComponent(projectId)}/clips/${encodeURIComponent(clipId)}/render`,
    { method: 'POST' },
  )
  const record = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return normalizeClip(record.clip ?? record.data ?? raw, projectId)
}

export { ApiError }
