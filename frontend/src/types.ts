export type ProjectStatus =
  | 'queued'
  | 'uploading'
  | 'processing'
  | 'analyzing'
  | 'rendering'
  | 'completed'
  | 'ready'
  | 'failed'
  | 'cancelled'
  | string

export interface HealthResponse {
  status?: string
  ready?: boolean
  message?: string
  device?: string
  gpu?: string | boolean | null
  version?: string
  [key: string]: unknown
}

export interface Stats {
  total_projects: number
  total_clips: number
  ready_clips?: number
  processing_projects: number
  completed_projects: number
  source_seconds?: number
  saved_minutes?: number
  storage_bytes?: number
}

export type ProjectGoal = 'viral' | 'education' | 'podcast' | 'gaming' | 'custom'
export type AspectRatio = '9:16' | '1:1' | '16:9'
export type CaptionPreset = 'impact' | 'minimal' | 'boxed' | 'clean'

export interface ProjectSettings {
  goal: ProjectGoal
  aspect_ratio: AspectRatio
  min_duration: number
  max_duration: number
  language: string
  clip_count: number
  caption_preset: CaptionPreset
  enable_captions: boolean
  auto_reframe: boolean
  remove_silence: boolean
  prompt: string
  min_score: number
  scene_sensitivity: number
}

export interface ScoreBreakdown {
  hook?: number
  flow?: number
  value?: number
  trend?: number | null
  safety?: number
  visual?: number
  [key: string]: number | null | undefined
}

export interface TranscriptSegment {
  start?: number
  end?: number
  text: string
  speaker?: string
}

export interface Clip {
  id: string
  project_id?: string
  title: string
  start_time: number
  end_time: number
  duration: number
  score: number
  status?: string
  aspect_ratio?: AspectRatio | string
  caption_preset?: CaptionPreset | string
  caption_text?: string
  text?: string
  transcript?: string | TranscriptSegment[]
  reasons: string[]
  scores: ScoreBreakdown
  thumbnail_url?: string | null
  video_url?: string | null
  download_url?: string | null
  srt_url?: string | null
  render_status?: string
  render_progress?: number
  render_error?: string | null
  enable_captions?: boolean
  caption_color?: string
  highlight_color?: string
  font_size?: number | null
  caption_position?: 'top' | 'middle' | 'bottom'
  focus_x?: number
  reframe?: {
    focus_x?: number
    engine?: string
    detections?: number
    [key: string]: unknown
  }
  favorite?: boolean
  error?: string | null
  [key: string]: unknown
}

export interface Project {
  id: string
  name: string
  status: ProjectStatus
  progress: number
  stage?: string
  message?: string | null
  error?: string | null
  created_at?: string
  updated_at?: string
  duration?: number
  file_size?: number
  source_url?: string | null
  thumbnail_url?: string | null
  settings?: Partial<ProjectSettings>
  stages?: Array<{
    key: string
    label: string
    status: 'queued' | 'running' | 'done' | 'error' | string
    progress: number
    detail?: string | null
  }>
  clips: Clip[]
  [key: string]: unknown
}

export interface ClipEditorSettings {
  title?: string
  favorite?: boolean
  start?: number
  end?: number
  aspect_ratio?: AspectRatio
  caption_preset?: CaptionPreset
  enable_captions?: boolean
  caption_color?: string
  highlight_color?: string
  font_size?: number
  caption_position?: 'top' | 'middle' | 'bottom'
  focus_x?: number
}

export interface ToastMessage {
  id: number
  kind: 'success' | 'error' | 'info'
  title: string
  description?: string
}
