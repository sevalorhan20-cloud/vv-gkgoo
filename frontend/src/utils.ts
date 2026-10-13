import type { Clip, Project, ScoreBreakdown, Stats } from './types'

const numberOr = (value: unknown, fallback = 0): number => {
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const stringOr = (value: unknown, fallback = ''): string =>
  typeof value === 'string' && value.trim() ? value : fallback

export function normalizeScore(value: unknown): number {
  const score = numberOr(value)
  return Math.round(Math.max(0, Math.min(score <= 1 && score > 0 ? score * 100 : score, 100)))
}

export function normalizeClip(raw: unknown, projectId?: string): Clip {
  const item = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const start = numberOr(item.start_time ?? item.start ?? item.start_seconds)
  const end = numberOr(item.end_time ?? item.end ?? item.end_seconds, start)
  const rawScores = (item.scores ?? item.score_breakdown ?? item.breakdown ?? {}) as ScoreBreakdown
  const rawReasons = item.reasons ?? item.explanations ?? item.highlights
  const reasons = Array.isArray(rawReasons)
    ? rawReasons.map((reason) => String(reason)).filter(Boolean)
    : typeof rawReasons === 'string'
      ? [rawReasons]
      : []

  return {
    ...item,
    id: String(item.id ?? item.clip_id ?? crypto.randomUUID()),
    project_id: stringOr(item.project_id, projectId),
    title: stringOr(item.title ?? item.headline, 'Başlıksız klip'),
    start_time: start,
    end_time: Math.max(end, start),
    duration: numberOr(item.duration, Math.max(0, end - start)),
    score: normalizeScore(item.score ?? item.final_score ?? item.virality_score),
    status: stringOr(item.render_status ?? item.status, 'stale'),
    aspect_ratio: stringOr(item.aspect_ratio, '9:16'),
    caption_preset: stringOr(item.caption_preset, 'impact'),
    caption_text: stringOr(item.caption_text ?? item.caption),
    text: stringOr(item.text),
    transcript: item.transcript as Clip['transcript'],
    reasons,
    scores: rawScores,
    thumbnail_url: stringOr(item.thumbnail_url) || null,
    video_url: stringOr(item.video_url) || null,
    download_url: stringOr(item.download_url) || null,
    srt_url: stringOr(item.srt_url) || null,
    render_status: stringOr(item.render_status ?? item.status, 'stale'),
    render_progress: numberOr(item.render_progress),
    render_error: stringOr(item.render_error) || null,
    enable_captions: item.enable_captions !== false,
    caption_color: stringOr(item.caption_color, '#FFFFFF'),
    highlight_color: stringOr(item.highlight_color, '#65E6B4'),
    font_size: item.font_size == null ? null : numberOr(item.font_size),
    caption_position: (stringOr(item.caption_position, 'bottom') as Clip['caption_position']),
    focus_x: numberOr(item.focus_x, 0.5),
    favorite: Boolean(item.favorite),
    error: stringOr(item.error ?? item.render_error) || null,
  }
}

export function normalizeProject(raw: unknown): Project {
  const item = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const rawClips = Array.isArray(item.clips)
    ? item.clips
    : Array.isArray(item.candidates)
      ? item.candidates
      : []
  const progressValue = numberOr(item.progress ?? item.progress_percent)
  const progress = progressValue > 0 && progressValue <= 1 ? progressValue * 100 : progressValue
  const id = String(item.id ?? item.project_id ?? '')
  const source = (item.source && typeof item.source === 'object' ? item.source : {}) as Record<string, unknown>

  return {
    ...item,
    id,
    name: stringOr(
      item.name ?? item.title ?? item.original_filename ?? item.filename ?? item.file_name,
      'İsimsiz proje',
    ),
    status: stringOr(item.status, 'queued').toLowerCase(),
    progress: Math.round(Math.max(0, Math.min(progress, 100))),
    stage: stringOr(item.stage ?? item.current_stage),
    message: stringOr(item.message) || null,
    error: stringOr(item.error ?? item.error_message) || null,
    created_at: stringOr(item.created_at) || undefined,
    updated_at: stringOr(item.updated_at) || undefined,
    duration: numberOr(item.duration ?? item.source_duration ?? source.duration),
    file_size: numberOr(item.file_size ?? item.size ?? source.size),
    source_url: stringOr(item.source_url ?? source.source_url) || null,
    thumbnail_url: stringOr(item.thumbnail_url ?? source.thumbnail_url) || null,
    settings: (item.settings && typeof item.settings === 'object' ? item.settings : {}) as Project['settings'],
    stages: Array.isArray(item.stages) ? item.stages as Project['stages'] : [],
    clips: rawClips.map((clip) => normalizeClip(clip, id)),
  }
}

export function normalizeStats(raw: unknown): Stats {
  const item = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  return {
    total_projects: numberOr(item.total_projects ?? item.projects_count ?? item.projects),
    total_clips: numberOr(item.total_clips ?? item.clips_count ?? item.clips),
    ready_clips: numberOr(item.ready_clips),
    processing_projects: numberOr(item.processing_projects ?? item.processing_count ?? item.processing),
    completed_projects: numberOr(item.completed_projects ?? item.completed_count ?? item.completed),
    source_seconds: numberOr(item.source_seconds) || undefined,
    saved_minutes: numberOr(item.saved_minutes ?? item.minutes_saved) || undefined,
    storage_bytes: numberOr(item.storage_bytes ?? item.storage_used ?? item.disk_usage) || undefined,
  }
}

export function formatDuration(totalSeconds?: number): string {
  const seconds = Math.max(0, Math.round(totalSeconds ?? 0))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = seconds % 60
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    : `${minutes}:${String(remainder).padStart(2, '0')}`
}

export function formatBytes(bytes?: number): string {
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} ${units[index]}`
}

export function formatDate(value?: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('tr-TR', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function isProjectActive(status?: string): boolean {
  return ['queued', 'uploading', 'processing', 'analyzing', 'transcribing', 'rendering', 'pending'].includes(
    (status ?? '').toLowerCase(),
  )
}

export function isProjectComplete(status?: string): boolean {
  return ['completed', 'complete', 'ready', 'done', 'success'].includes((status ?? '').toLowerCase())
}

export function isProjectFailed(status?: string): boolean {
  return ['failed', 'error', 'cancelled', 'canceled', 'interrupted'].includes((status ?? '').toLowerCase())
}

export function getProjectStatusLabel(status?: string): string {
  const labels: Record<string, string> = {
    queued: 'Sırada',
    uploading: 'Yükleniyor',
    processing: 'İşleniyor',
    analyzing: 'Analiz ediliyor',
    transcribing: 'Yazıya çevriliyor',
    rendering: 'Hazırlanıyor',
    completed: 'Tamamlandı',
    complete: 'Tamamlandı',
    ready: 'Hazır',
    done: 'Hazır',
    failed: 'Başarısız',
    error: 'Hata',
    cancelled: 'İptal edildi',
    interrupted: 'Yarım kaldı',
  }
  return labels[(status ?? '').toLowerCase()] ?? 'Bekleniyor'
}

export function getScoreTone(score: number): 'high' | 'mid' | 'low' {
  if (score >= 80) return 'high'
  if (score >= 60) return 'mid'
  return 'low'
}
