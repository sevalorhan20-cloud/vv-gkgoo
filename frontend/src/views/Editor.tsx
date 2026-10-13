import {
  AlignCenter,
  ArrowLeft,
  Captions,
  Check,
  ChevronDown,
  Download,
  Film,
  Focus,
  Gauge,
  Layers3,
  LoaderCircle,
  Maximize2,
  Pause,
  Play,
  RotateCcw,
  Save,
  Scissors,
  SlidersHorizontal,
  Sparkles,
  Type,
  Undo2,
  WandSparkles,
} from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { getProject, renderClip, updateClip } from '../api'
import { ErrorState, LoadingState, StatusPill } from '../components/Common'
import { useToast } from '../components/Toast'
import type { AspectRatio, CaptionPreset, Clip, ClipEditorSettings, Project, TranscriptSegment } from '../types'
import { formatDuration, isProjectActive } from '../utils'

interface EditorProps {
  projectId: string
  clipId: string
  navigate: (path: string) => void
  onDirtyChange: (dirty: boolean) => void
}

interface EditorState {
  title: string
  start: number
  end: number
  aspect_ratio: AspectRatio
  caption_preset: CaptionPreset
  enable_captions: boolean
  caption_position: 'top' | 'middle' | 'bottom'
  caption_color: string
  highlight_color: string
  font_size: number
  focus_x: number
}

export function Editor({ projectId, clipId, navigate, onDirtyChange }: EditorProps) {
  const [project, setProject] = useState<Project | null>(null)
  const [clip, setClip] = useState<Clip | null>(null)
  const [editor, setEditor] = useState<EditorState | null>(null)
  const [savedState, setSavedState] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [rendering, setRendering] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [activeTool, setActiveTool] = useState<'trim' | 'captions' | 'focus'>('trim')
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLDivElement>(null)
  const lastFailedSaveRef = useRef<string | null>(null)
  const { notify } = useToast()

  const hydrate = useCallback(async () => {
    setError(null)
    try {
      const nextProject = await getProject(projectId)
      const nextClip = nextProject.clips.find((item) => item.id === clipId)
      if (!nextClip) throw new Error('Klip bu projede bulunamadı.')
      const nextEditor = editorFromClip(nextClip)
      setProject(nextProject)
      setClip(nextClip)
      setEditor(nextEditor)
      setSavedState(JSON.stringify(nextEditor))
      lastFailedSaveRef.current = null
      setCurrentTime(nextEditor.start)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Editör açılamadı.')
    } finally {
      setLoading(false)
    }
  }, [clipId, projectId])

  useEffect(() => { void hydrate() }, [hydrate])

  const dirty = editor ? JSON.stringify(editor) !== savedState : false

  useLayoutEffect(() => {
    onDirtyChange(dirty)
  }, [dirty, onDirtyChange])

  useEffect(() => () => onDirtyChange(false), [onDirtyChange])

  const save = useCallback(async (quiet = false): Promise<Clip | null> => {
    if (!editor || !clip || saving) return null
    const snapshot = JSON.stringify(editor)
    setSaving(true)
    const payload: ClipEditorSettings = {
      title: editor.title.trim() || clip.title,
      start: Number(editor.start.toFixed(3)),
      end: Number(editor.end.toFixed(3)),
      aspect_ratio: editor.aspect_ratio,
      caption_preset: editor.caption_preset,
      enable_captions: editor.enable_captions,
      caption_position: editor.caption_position,
      caption_color: editor.caption_color,
      highlight_color: editor.highlight_color,
      font_size: editor.font_size,
      focus_x: editor.focus_x,
    }
    try {
      const updated = await updateClip(projectId, clipId, payload)
      setClip((current) => current ? { ...current, ...updated } : updated)
      setSavedState(snapshot)
      lastFailedSaveRef.current = null
      if (!quiet) notify({ kind: 'success', title: 'Değişiklikler yerelde kaydedildi' })
      return updated
    } catch (err) {
      lastFailedSaveRef.current = snapshot
      notify({ kind: 'error', title: 'Değişiklikler kaydedilemedi', description: err instanceof Error ? err.message : undefined })
      return null
    } finally {
      setSaving(false)
    }
  }, [clip, clipId, editor, notify, projectId, saving])

  useEffect(() => {
    if (!dirty || saving || !editor) return
    if (lastFailedSaveRef.current === JSON.stringify(editor)) return
    const timer = window.setTimeout(() => void save(true), 1400)
    return () => window.clearTimeout(timer)
  }, [dirty, editor, save, saving])

  useEffect(() => {
    if (!clip || !isProjectActive(clip.render_status)) return
    const timer = window.setInterval(async () => {
      try {
        const nextProject = await getProject(projectId)
        const nextClip = nextProject.clips.find((item) => item.id === clipId)
        if (nextClip) {
          setProject(nextProject)
          setClip(nextClip)
          if (!isProjectActive(nextClip.render_status)) setRendering(false)
        }
      } catch {
        // A transient poll failure should not interrupt editing.
      }
    }, 2200)
    return () => window.clearInterval(timer)
  }, [clip?.render_status, clipId, projectId])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        void save()
        return
      }
      if (target.matches('input, textarea, select, [contenteditable="true"]')) return
      if (event.code === 'Space') {
        event.preventDefault()
        togglePlayback()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  const update = <K extends keyof EditorState>(key: K, value: EditorState[K]) => {
    lastFailedSaveRef.current = null
    setEditor((current) => current ? { ...current, [key]: value } : current)
  }

  const togglePlayback = () => {
    const video = videoRef.current
    if (!video || !editor) return
    if (video.paused) {
      if (video.currentTime < editor.start || video.currentTime >= editor.end) video.currentTime = editor.start
      void video.play()
      setPlaying(true)
    } else {
      video.pause()
      setPlaying(false)
    }
  }

  const handleRender = async () => {
    if (!editor || !clip) return
    setRendering(true)
    try {
      if (dirty) {
        const saved = await save(true)
        if (!saved) { setRendering(false); return }
      }
      const queued = await renderClip(projectId, clipId)
      setClip((current) => current ? { ...current, ...queued } : queued)
      notify({ kind: 'info', title: 'Klip hazırlanıyor', description: 'Render yerel motorda arka planda devam ediyor.' })
    } catch (err) {
      setRendering(false)
      notify({ kind: 'error', title: 'Render başlatılamadı', description: err instanceof Error ? err.message : undefined })
    }
  }

  if (loading) return <div className="page"><LoadingState label="Editör hazırlanıyor…" /></div>
  if (error || !project || !clip || !editor) return <div className="page"><ErrorState message={error ?? 'Klip bulunamadı.'} onRetry={() => void hydrate()} /></div>

  const sourceDuration = Math.max(project.duration ?? editor.end, editor.end)
  const duration = editor.end - editor.start
  const transcript = transcriptText(clip)
  const renderActive = rendering || isProjectActive(clip.render_status)
  const automaticFocus = Math.max(0, Math.min(1, clip.reframe?.focus_x ?? 0.5))

  return (
    <div className="editor-page">
      <header className="editor-header">
        <button className="button button--ghost" onClick={() => navigate(`/projects/${projectId}`)}><ArrowLeft size={17} /> Sonuçlara dön</button>
        <div className="editor-title">
          <input value={editor.title} onChange={(event) => update('title', event.target.value)} maxLength={120} aria-label="Klip başlığı" />
          <span>{saving ? <><LoaderCircle className="spin" size={13} /> Kaydediliyor…</> : dirty ? 'Kaydedilmemiş değişiklik' : <><Check size={13} /> Yerelde kaydedildi</>}</span>
        </div>
        <div className="editor-header__actions">
          <button className="button button--secondary editor-save" onClick={() => void save()} disabled={saving || !dirty}><Save size={16} /> Kaydet</button>
          {clip.download_url && clip.render_status === 'ready' && !dirty ? (
            <a className="button button--secondary" href={clip.download_url} download><Download size={16} /> İndir</a>
          ) : null}
          <button className="button button--primary" onClick={() => void handleRender()} disabled={renderActive || saving}>
            {renderActive ? <LoaderCircle className="spin" size={16} /> : <WandSparkles size={16} />}
            {renderActive ? `%${clip.render_progress ?? 0} hazırlanıyor` : 'Render al'}
          </button>
        </div>
      </header>

      <div className="editor-workspace">
        <aside className="editor-tools" aria-label="Editör araçları">
          <button className={activeTool === 'trim' ? 'active' : ''} onClick={() => setActiveTool('trim')}><Scissors size={19} /><span>Kes</span></button>
          <button className={activeTool === 'captions' ? 'active' : ''} onClick={() => setActiveTool('captions')}><Captions size={19} /><span>Altyazı</span></button>
          <button className={activeTool === 'focus' ? 'active' : ''} onClick={() => setActiveTool('focus')}><Focus size={19} /><span>Kadraj</span></button>
        </aside>

        <aside className="editor-panel editor-panel--left">
          {activeTool === 'trim' && (
            <>
              <PanelTitle icon={<Scissors size={17} />} title="Klip aralığı" description="Başlangıç ve bitişi doğal konuşma sınırlarında tutun." />
              <div className="time-inputs">
                <label><span>Başlangıç</span><input type="number" min={0} max={editor.end - 0.5} step={0.1} value={Number(editor.start.toFixed(1))} onChange={(event) => update('start', Math.min(Number(event.target.value), editor.end - 0.5))} /></label>
                <span>—</span>
                <label><span>Bitiş</span><input type="number" min={editor.start + 0.5} max={sourceDuration} step={0.1} value={Number(editor.end.toFixed(1))} onChange={(event) => update('end', Math.max(Number(event.target.value), editor.start + 0.5))} /></label>
              </div>
              <div className="clip-length"><span>Klip uzunluğu</span><strong>{formatDuration(duration)}</strong></div>
              <div className="transcript-panel">
                <div className="panel-label"><Type size={15} /> Klip metni</div>
                {transcript ? <p>{transcript}</p> : <div className="transcript-empty">Bu klip için konuşma metni bulunamadı.</div>}
              </div>
            </>
          )}
          {activeTool === 'captions' && (
            <>
              <PanelTitle icon={<Captions size={17} />} title="Altyazılar" description="Okunaklı ve markanıza uygun bir stil seçin." />
              <label className="toggle-row toggle-row--panel"><span><strong>Altyazıyı göster</strong><small>Videoya kalıcı olarak işlenir</small></span><input type="checkbox" checked={editor.enable_captions} onChange={(event) => update('enable_captions', event.target.checked)} /><i /></label>
              <fieldset className="editor-control" disabled={!editor.enable_captions}>
                <legend>Stil</legend>
                <div className="editor-presets">
                  {([
                    ['impact', 'Vurgu'], ['clean', 'Temiz'], ['boxed', 'Kutulu'], ['minimal', 'Minimal'],
                  ] as Array<[CaptionPreset, string]>).map(([preset, label]) => (
                    <label className={`${editor.caption_preset === preset ? 'selected' : ''} caption-preset--${preset}`} key={preset}><input type="radio" name="editor-preset" checked={editor.caption_preset === preset} onChange={() => update('caption_preset', preset)} /><span>Aa</span><strong>{label}</strong><Check size={14} /></label>
                  ))}
                </div>
              </fieldset>
              <fieldset className="editor-control" disabled={!editor.enable_captions}>
                <legend>Konum</legend>
                <div className="button-segments">{(['top', 'middle', 'bottom'] as const).map((position) => <button className={editor.caption_position === position ? 'selected' : ''} onClick={() => update('caption_position', position)} key={position}>{position === 'top' ? 'Üst' : position === 'middle' ? 'Orta' : 'Alt'}</button>)}</div>
              </fieldset>
              <label className="range-control"><span>Yazı boyutu <strong>{editor.font_size}px</strong></span><input type="range" min={28} max={110} value={editor.font_size} onChange={(event) => update('font_size', Number(event.target.value))} disabled={!editor.enable_captions} /></label>
              <div className="color-controls"><label><span>Metin</span><input type="color" value={editor.caption_color} onChange={(event) => update('caption_color', event.target.value)} /></label><label><span>Vurgu</span><input type="color" value={editor.highlight_color} onChange={(event) => update('highlight_color', event.target.value)} /></label></div>
            </>
          )}
          {activeTool === 'focus' && (
            <>
              <PanelTitle icon={<Focus size={17} />} title="Akıllı kadraj" description="Dikey kesimin yatay odağını gerekirse elle düzeltin." />
              <label className="range-control"><span>Yatay odak <strong>%{Math.round(editor.focus_x * 100)}</strong></span><input type="range" min={0} max={1} step={0.01} value={editor.focus_x} onChange={(event) => update('focus_x', Number(event.target.value))} /></label>
              <button className="button button--secondary button--full" onClick={() => update('focus_x', automaticFocus)}><Sparkles size={16} /> Otomatik odağa dön</button>
              <div className="safe-zone-note"><Focus size={17} /><span>Kesikli çizgi, platform arayüzlerinin kapatabileceği güvenli alanı gösterir.</span></div>
            </>
          )}
        </aside>

        <main className="editor-canvas-area">
          <div className="canvas-toolbar">
            <div className="ratio-switcher" aria-label="En-boy oranı">
              {(['9:16', '1:1', '16:9'] as AspectRatio[]).map((ratio) => <button className={editor.aspect_ratio === ratio ? 'active' : ''} onClick={() => update('aspect_ratio', ratio)} key={ratio}><span className={`ratio-icon ratio-icon--${ratio.replace(':', '-')}`} />{ratio}</button>)}
            </div>
            <button className="icon-button" aria-label="Önizlemeyi tam ekran aç" onClick={() => canvasRef.current?.requestFullscreen?.()}><Maximize2 size={17} /></button>
          </div>
          <div ref={canvasRef} className={`video-canvas video-canvas--${editor.aspect_ratio.replace(':', '-')}`}>
            <video
              ref={videoRef}
              src={project.source_url ?? clip.video_url ?? undefined}
              poster={clip.thumbnail_url ?? project.thumbnail_url ?? undefined}
              style={{ objectPosition: `${editor.focus_x * 100}% center` }}
              preload="metadata"
              onLoadedMetadata={(event) => { event.currentTarget.currentTime = editor.start; setCurrentTime(editor.start) }}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onTimeUpdate={(event) => {
                const time = event.currentTarget.currentTime
                setCurrentTime(time)
                if (time >= editor.end) { event.currentTarget.pause(); event.currentTarget.currentTime = editor.start }
              }}
            />
            <span className="safe-zone" aria-hidden="true" />
            <span className="focus-guide" style={{ left: `${editor.focus_x * 100}%` }} aria-hidden="true" />
            {editor.enable_captions && transcript && (
              <span
                className={`canvas-caption canvas-caption--${editor.caption_preset} canvas-caption--${editor.caption_position}`}
                style={{ color: editor.caption_color, '--highlight': editor.highlight_color, fontSize: `${Math.max(13, editor.font_size * 0.29)}px` } as React.CSSProperties}
              >
                {captionSample(transcript)}
              </span>
            )}
            {!project.source_url && !clip.video_url && <div className="video-canvas__empty"><Film size={35} /><span>Video önizlemesi kullanılamıyor</span></div>}
          </div>
          <div className="player-controls">
            <button className="player-play" onClick={togglePlayback} aria-label={playing ? 'Duraklat' : 'Oynat'}>{playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}</button>
            <span>{formatDuration(Math.max(0, currentTime - editor.start))} / {formatDuration(duration)}</span>
            <span className="player-controls__spacer" />
            <span className="shortcut-hint">Boşluk: oynat/duraklat</span>
          </div>
        </main>

        <aside className="editor-panel editor-panel--right">
          <PanelTitle icon={<SlidersHorizontal size={17} />} title="Klip bilgisi" description="Çıktı ve tahmin özeti." />
          <div className="inspector-score"><span className="inspector-score__number">{clip.score}</span><div><strong>Öne çıkma puanı</strong><small>Tahmini · garanti değildir</small></div></div>
          <dl className="inspector-list"><div><dt>Kaynak aralığı</dt><dd>{formatDuration(editor.start)} – {formatDuration(editor.end)}</dd></div><div><dt>Çıktı oranı</dt><dd>{editor.aspect_ratio}</dd></div><div><dt>Render</dt><dd><StatusPill status={clip.render_status} progress={clip.render_progress} /></dd></div></dl>
          {clip.reasons.length > 0 && <div className="editor-reasons"><span className="panel-label"><Gauge size={15} /> Neden seçildi?</span>{clip.reasons.map((reason) => <p key={reason}><Check size={14} /> {reason}</p>)}</div>}
          {clip.render_error && <div className="inline-error">{clip.render_error}</div>}
          {clip.download_url && clip.render_status === 'ready' && !dirty && <a className="button button--primary button--full" href={clip.download_url} download><Download size={16} /> MP4 indir</a>}
          {clip.srt_url && clip.render_status === 'ready' && !dirty && <a className="button button--secondary button--full" href={clip.srt_url} download><Captions size={16} /> SRT indir</a>}
        </aside>
      </div>

      <footer className="editor-timeline">
        <div className="timeline-heading"><span><Layers3 size={15} /> Zaman çizelgesi</span><strong>{formatDuration(editor.start)} — {formatDuration(editor.end)}</strong></div>
        <div className="timeline-track">
          <div className="timeline-wave">{Array.from({ length: 90 }, (_, index) => <i style={{ height: `${18 + ((index * 31) % 72)}%` }} key={index} />)}</div>
          <span className="timeline-selection" style={{ left: `${editor.start / sourceDuration * 100}%`, width: `${duration / sourceDuration * 100}%` }}><b className="handle handle--left" /><b className="handle handle--right" /></span>
          <span className="timeline-playhead" style={{ left: `${currentTime / sourceDuration * 100}%` }} />
        </div>
        <div className="timeline-ranges">
          <label><span className="sr-only">Başlangıç zamanı</span><input type="range" min={0} max={Math.max(0.5, editor.end - 0.5)} step={0.1} value={editor.start} onChange={(event) => { const value = Number(event.target.value); update('start', value); if (videoRef.current) videoRef.current.currentTime = value }} /></label>
          <label><span className="sr-only">Bitiş zamanı</span><input type="range" min={editor.start + 0.5} max={sourceDuration} step={0.1} value={editor.end} onChange={(event) => update('end', Number(event.target.value))} /></label>
        </div>
      </footer>
    </div>
  )
}

function PanelTitle({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return <div className="panel-title"><span>{icon}</span><div><h2>{title}</h2><p>{description}</p></div></div>
}

function editorFromClip(clip: Clip): EditorState {
  return {
    title: clip.title,
    start: clip.start_time,
    end: clip.end_time,
    aspect_ratio: (['9:16', '1:1', '16:9'].includes(String(clip.aspect_ratio)) ? clip.aspect_ratio : '9:16') as AspectRatio,
    caption_preset: (['impact', 'clean', 'boxed', 'minimal'].includes(String(clip.caption_preset)) ? clip.caption_preset : 'impact') as CaptionPreset,
    enable_captions: clip.enable_captions !== false,
    caption_position: clip.caption_position ?? 'bottom',
    caption_color: clip.caption_color ?? '#FFFFFF',
    highlight_color: clip.highlight_color ?? '#65E6B4',
    font_size: clip.font_size ?? 56,
    focus_x: clip.focus_x ?? 0.5,
  }
}

function transcriptText(clip: Clip): string {
  if (typeof clip.text === 'string' && clip.text.trim()) return clip.text.trim()
  if (typeof clip.transcript === 'string') return clip.transcript.trim()
  if (Array.isArray(clip.transcript)) return clip.transcript.map((segment: TranscriptSegment) => segment.text).join(' ').trim()
  return ''
}

function captionSample(text: string): React.ReactNode {
  const words = text.split(/\s+/).filter(Boolean).slice(0, 7)
  return words.map((word, index) => index === Math.min(2, words.length - 1) ? <em key={`${word}-${index}`}>{word} </em> : `${word} `)
}
