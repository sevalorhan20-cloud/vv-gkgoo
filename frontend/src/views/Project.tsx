import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Captions,
  Check,
  CheckCircle2,
  ChevronDown,
  Circle,
  Clock3,
  Download,
  Edit3,
  Eye,
  Film,
  Filter,
  Flame,
  LayoutGrid,
  Lightbulb,
  ListFilter,
  LoaderCircle,
  MoreHorizontal,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  WandSparkles,
  X,
  Zap,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { deleteProject, getProject, renderClip, retryProject } from '../api'
import { EmptyState, ErrorState, LoadingState, ScoreRing, StatusPill } from '../components/Common'
import { useToast } from '../components/Toast'
import type { Clip, Project as ProjectType } from '../types'
import {
  formatDate,
  formatDuration,
  getProjectStatusLabel,
  isProjectActive,
  isProjectComplete,
  isProjectFailed,
  normalizeScore,
} from '../utils'

interface ProjectProps {
  projectId: string
  navigate: (path: string) => void
}

const pipelineStages = [
  { key: 'prepare', label: 'Video hazırlanıyor', description: 'Codec ve ses akışı denetleniyor', threshold: 8 },
  { key: 'transcribe', label: 'Konuşma yazıya çevriliyor', description: 'Kelime zamanları ve cümleler çıkarılıyor', threshold: 32 },
  { key: 'analyze', label: 'Sahne ve anlar algılanıyor', description: 'Görüntü, tempo ve bağlam birlikte inceleniyor', threshold: 58 },
  { key: 'score', label: 'Güçlü anlar puanlanıyor', description: 'Giriş, akış ve bilgi değeri ölçülüyor', threshold: 80 },
  { key: 'render', label: 'Klipler hazırlanıyor', description: 'Kadraj ve altyazı ayarları oluşturuluyor', threshold: 100 },
]

export function Project({ projectId, navigate }: ProjectProps) {
  const [project, setProject] = useState<ProjectType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const { notify } = useToast()

  const load = useCallback(async (silent = false) => {
    if (!silent) setError(null)
    try {
      const next = await getProject(projectId)
      setProject(next)
      setError(null)
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : 'Proje yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    setLoading(true)
    setProject(null)
    void load()
  }, [load])

  useEffect(() => {
    const needsFastPolling = project ? isProjectActive(project.status) || project.clips.some((clip) => isProjectActive(clip.status)) : true
    const timer = window.setInterval(() => void load(true), needsFastPolling ? 2500 : 12000)
    return () => window.clearInterval(timer)
  }, [load, project?.status, project?.clips])

  const handleRetry = async () => {
    setRetrying(true)
    try {
      const next = await retryProject(projectId)
      setProject(next)
      notify({ kind: 'success', title: 'Analiz yeniden başlatıldı' })
    } catch (err) {
      notify({ kind: 'error', title: 'Tekrar başlatılamadı', description: err instanceof Error ? err.message : undefined })
    } finally {
      setRetrying(false)
    }
  }

  const handleDelete = async () => {
    if (!project || !window.confirm(`“${project.name}” projesi kalıcı olarak silinsin mi?`)) return
    try {
      await deleteProject(project.id)
      notify({ kind: 'success', title: 'Proje silindi' })
      navigate('/')
    } catch (err) {
      notify({ kind: 'error', title: 'Proje silinemedi', description: err instanceof Error ? err.message : undefined })
    }
  }

  if (loading && !project) return <div className="page"><LoadingState label="Proje açılıyor…" /></div>
  if (error && !project) return <div className="page"><ErrorState message={error} onRetry={() => void load()} /></div>
  if (!project) return null

  if (isProjectFailed(project.status)) {
    return (
      <div className="page project-page">
        <ProjectHeader project={project} navigate={navigate} onDelete={() => void handleDelete()} />
        <section className="failure-card">
          <span className="failure-card__icon"><AlertTriangle size={26} /></span>
          <div><span className="eyebrow eyebrow--danger">Analiz durdu</span><h1>Video işlenemedi</h1><p>{project.error || 'Yerel motor bu videoyu işlerken beklenmeyen bir sorunla karşılaştı.'}</p></div>
          <div className="failure-card__actions">
            <button className="button button--primary" onClick={() => void handleRetry()} disabled={retrying}>{retrying ? <LoaderCircle className="spin" size={17} /> : <RotateCcw size={17} />} Tekrar dene</button>
            <button className="button button--secondary" onClick={() => navigate('/new')}>Başka video seç</button>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="page project-page">
      <ProjectHeader project={project} navigate={navigate} onDelete={() => void handleDelete()} />
      {isProjectComplete(project.status) ? (
        <Results project={project} navigate={navigate} refresh={() => void load(true)} />
      ) : (
        <Processing project={project} navigate={navigate} />
      )}
    </div>
  )
}

function ProjectHeader({ project, navigate, onDelete }: { project: ProjectType; navigate: (path: string) => void; onDelete: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false)
  return (
    <header className="project-header">
      <button className="back-button" onClick={() => navigate('/')}><ArrowLeft size={17} /> Projeler</button>
      <div className="project-header__main">
        <div><div className="project-header__title"><h1>{project.name}</h1><StatusPill status={project.status} progress={project.progress} /></div><p>{formatDate(project.created_at)}{project.duration ? ` · ${formatDuration(project.duration)}` : ''} · Yerel proje</p></div>
        <div className="project-header__actions">
          {isProjectComplete(project.status) && <button className="button button--primary" onClick={() => document.getElementById('clip-results')?.scrollIntoView({ behavior: 'smooth' })}><Sparkles size={17} /> Klipleri incele</button>}
          <div className="relative-menu">
            <button className="icon-button" aria-label="Proje seçenekleri" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><MoreHorizontal size={20} /></button>
            {menuOpen && <div className="dropdown-menu dropdown-menu--right"><button className="dropdown-menu__danger" onClick={onDelete}><Trash2 size={16} /> Projeyi sil</button></div>}
          </div>
        </div>
      </div>
    </header>
  )
}

function Processing({ project, navigate }: { project: ProjectType; navigate: (path: string) => void }) {
  const currentIndex = pipelineStages.findIndex((stage) => project.progress < stage.threshold)
  const stageIndex = currentIndex === -1 ? pipelineStages.length - 1 : Math.max(0, currentIndex)
  const candidateClips = project.clips.slice(0, 3)

  return (
    <>
      <section className="processing-hero">
        <div className="processing-hero__top">
          <div><span className="eyebrow"><WandSparkles size={14} /> Analiz sürüyor</span><h2>{project.message || 'En güçlü anlar aranıyor…'}</h2><p>Bu sayfadan ayrılabilirsiniz; yerel işlem arka planda devam eder.</p></div>
          <div className="progress-orbit" style={{ '--progress': `${project.progress * 3.6}deg` } as React.CSSProperties}><strong>%{project.progress}</strong><span>tamamlandı</span></div>
        </div>
        <div className="overall-progress"><i style={{ width: `${project.progress}%` }} /></div>
      </section>

      <div className="processing-layout">
        <section className="analysis-preview panel-card">
          <div className="panel-card__heading"><div><span className="eyebrow eyebrow--muted">Kaynak video</span><h3>Canlı analiz</h3></div><span className="live-badge"><i /> İŞLENİYOR</span></div>
          <div className="analysis-player">
            {project.source_url ? (
              <video src={project.source_url} poster={project.thumbnail_url ?? undefined} controls preload="metadata" />
            ) : project.thumbnail_url ? (
              <img src={project.thumbnail_url} alt="Kaynak video önizlemesi" />
            ) : (
              <div className="video-placeholder"><Film size={38} /><span>Önizleme hazırlanıyor</span></div>
            )}
            <span className="scan-line" aria-hidden="true" />
          </div>
          <div className="analysis-wave" aria-label={`Analiz yüzde ${project.progress}`}>
            {Array.from({ length: 48 }, (_, index) => (
              <i className={index / 48 * 100 <= project.progress ? 'analyzed' : ''} style={{ height: `${20 + ((index * 37) % 55)}%` }} key={index} />
            ))}
            <span style={{ left: `${project.progress}%` }} />
          </div>
          <div className="analysis-signals">
            <span><Eye size={15} /> Görsel hareket</span><span><Captions size={15} /> Konuşma</span><span><Zap size={15} /> Enerji</span>
          </div>
        </section>

        <section className="pipeline-card panel-card">
          <div className="panel-card__heading"><div><span className="eyebrow eyebrow--muted">İşlem hattı</span><h3>Analiz adımları</h3></div><Clock3 size={19} /></div>
          <ol className="pipeline-list">
            {pipelineStages.map((stage, index) => {
              const actual = project.stages?.find((item) => item.key === stage.key)
              const done = actual ? actual.status === 'done' : project.progress >= stage.threshold
              const active = actual ? actual.status === 'running' : index === stageIndex && !done
              const failed = actual?.status === 'error'
              return (
                <li className={`${done ? 'done' : ''} ${active ? 'active' : ''} ${failed ? 'error' : ''}`} key={stage.key}>
                  <span className="pipeline-list__marker">{done ? <Check size={15} /> : active ? <LoaderCircle className="spin" size={16} /> : failed ? <AlertTriangle size={15} /> : <Circle size={12} />}</span>
                  <div><strong>{actual?.label || stage.label}</strong><small>{actual?.detail || stage.description}</small></div>
                  {done ? <span className="pipeline-list__done">Tamam</span> : active && actual ? <span className="pipeline-list__done">%{actual.progress}</span> : null}
                </li>
              )
            })}
          </ol>
          <div className="local-processing-note"><ShieldCheck size={18} /><span><strong>Yerel ve özel</strong> · Analiz verileri cihazınızda kalır.</span></div>
        </section>
      </div>

      {candidateClips.length > 0 && (
        <section className="found-candidates">
          <div className="section-heading"><div><span className="eyebrow eyebrow--muted">İlk bulgular</span><h2>{candidateClips.length} aday an bulundu</h2></div><span className="subtle-label">Analiz tamamlandıkça güncellenir</span></div>
          <div className="candidate-row">
            {candidateClips.map((clip) => (
              <button className="candidate-mini" key={clip.id} onClick={() => navigate(`/projects/${project.id}/clips/${clip.id}/edit`)}>
                <span className="candidate-mini__thumb">{clip.thumbnail_url ? <img src={clip.thumbnail_url} alt="" /> : <Film size={22} />}<ScoreRing score={clip.score} size="small" /></span>
                <span><strong>{clip.title}</strong><small>{formatDuration(clip.duration)} · {formatDuration(clip.start_time)}</small></span>
                <ArrowRight size={16} />
              </button>
            ))}
          </div>
        </section>
      )}
    </>
  )
}

function Results({ project, navigate, refresh }: { project: ProjectType; navigate: (path: string) => void; refresh: () => void }) {
  const [query, setQuery] = useState('')
  const [ratio, setRatio] = useState('all')
  const [minimum, setMinimum] = useState(0)
  const [sort, setSort] = useState<'score' | 'time'>('score')
  const [filterOpen, setFilterOpen] = useState(false)
  const [renderingId, setRenderingId] = useState<string | null>(null)
  const { notify } = useToast()

  const clips = useMemo(() => {
    return project.clips
      .filter((clip) => clip.title.toLocaleLowerCase('tr-TR').includes(query.toLocaleLowerCase('tr-TR')))
      .filter((clip) => ratio === 'all' || clip.aspect_ratio === ratio)
      .filter((clip) => clip.score >= minimum)
      .sort((a, b) => sort === 'score' ? b.score - a.score : a.start_time - b.start_time)
  }, [project.clips, query, ratio, minimum, sort])

  const handleRender = async (clip: Clip) => {
    setRenderingId(clip.id)
    try {
      const rendered = await renderClip(project.id, clip.id)
      const ready = rendered.render_status === 'ready'
      notify({ kind: ready ? 'success' : 'info', title: ready ? 'Klip hazır' : 'Render sırasına alındı', description: ready ? 'Dosyayı şimdi indirebilirsiniz.' : 'İşlem yerel motorda devam ediyor.' })
      refresh()
    } catch (err) {
      notify({ kind: 'error', title: 'Render başlatılamadı', description: err instanceof Error ? err.message : undefined })
    } finally {
      setRenderingId(null)
    }
  }

  return (
    <section className="results-section" id="clip-results">
      <div className="results-summary">
        <div><span className="eyebrow"><Sparkles size={14} /> Analiz tamamlandı</span><h2>{project.clips.length ? `${project.clips.length} güçlü an bulundu` : 'Analiz tamamlandı'}</h2><p>{project.clips.length ? 'Bağlamı korunmuş adayları puanlarına göre inceleyin ve düzenleyin.' : 'Bu videoda ayarlarınıza uyan bir klip bulunamadı.'}</p></div>
        {project.clips.length > 0 && <div className="best-score"><ScoreRing score={Math.max(...project.clips.map((clip) => clip.score))} size="large" /><span><strong>En yüksek puan</strong><small>Kesin izlenme garantisi değildir</small></span></div>}
      </div>

      {project.clips.length === 0 ? (
        <EmptyState icon={<Film size={25} />} title="Uygun an bulunamadı" description="Farklı süre veya içerik hedefiyle yeni bir analiz başlatabilirsiniz." action={<button className="button button--primary" onClick={() => navigate('/new')}>Yeni analiz</button>} />
      ) : (
        <>
          <div className="results-toolbar">
            <label className="search-field"><Search size={17} /><span className="sr-only">Kliplerde ara</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Kliplerde ara…" />{query && <button onClick={() => setQuery('')} aria-label="Aramayı temizle"><X size={15} /></button>}</label>
            <button className={`button button--secondary filter-button ${filterOpen ? 'active' : ''}`} onClick={() => setFilterOpen(!filterOpen)}><Filter size={16} /> Filtrele</button>
            <div className={`filter-controls ${filterOpen ? 'filter-controls--open' : ''}`}>
              <label><span className="sr-only">En-boy oranı</span><select value={ratio} onChange={(event) => setRatio(event.target.value)}><option value="all">Tüm oranlar</option><option value="9:16">9:16</option><option value="1:1">1:1</option><option value="16:9">16:9</option></select></label>
              <label><span className="sr-only">Minimum puan</span><select value={minimum} onChange={(event) => setMinimum(Number(event.target.value))}><option value={0}>Tüm puanlar</option><option value={60}>60+ puan</option><option value={75}>75+ puan</option><option value={90}>90+ puan</option></select></label>
              <label><span className="sr-only">Sıralama</span><select value={sort} onChange={(event) => setSort(event.target.value as 'score' | 'time')}><option value="score">En yüksek puan</option><option value="time">Video sırası</option></select></label>
            </div>
            <span className="results-count"><LayoutGrid size={16} /> {clips.length} klip</span>
          </div>

          {clips.length === 0 ? (
            <EmptyState icon={<ListFilter size={24} />} title="Bu filtrelerle sonuç yok" description="Aramayı veya puan filtrelerini temizleyip tekrar deneyin." action={<button className="button button--secondary" onClick={() => { setQuery(''); setRatio('all'); setMinimum(0) }}>Filtreleri temizle</button>} />
          ) : (
            <div className="clips-grid">
              {clips.map((clip, index) => (
                <ClipCard
                  clip={clip}
                  rank={[...project.clips].sort((a, b) => b.score - a.score).findIndex((item) => item.id === clip.id) + 1 || index + 1}
                  key={clip.id}
                  onEdit={() => navigate(`/projects/${project.id}/clips/${clip.id}/edit`)}
                  onRender={() => void handleRender(clip)}
                  rendering={renderingId === clip.id || isProjectActive(clip.status)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}

function ClipCard({ clip, rank, onEdit, onRender, rendering }: { clip: Clip; rank: number; onEdit: () => void; onRender: () => void; rendering: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const reasonFallback = [clip.score >= 80 ? 'Güçlü giriş' : 'Net bağlam', 'Akıcı anlatım', 'Paylaşılabilir an']
  const reasons = clip.reasons.length ? clip.reasons.slice(0, 3) : reasonFallback.slice(0, 2)
  const breakdown = Object.entries(clip.scores).filter((entry): entry is [string, number] => typeof entry[1] === 'number')

  return (
    <article className="clip-card">
      <div className={`clip-card__media clip-card__media--${String(clip.aspect_ratio ?? '9:16').replace(':', '-')}`} onMouseEnter={() => videoRef.current?.play().catch(() => undefined)} onMouseLeave={() => { if (videoRef.current) { videoRef.current.pause(); videoRef.current.currentTime = 0 } }}>
        {clip.video_url ? <video ref={videoRef} src={clip.video_url} poster={clip.thumbnail_url ?? undefined} muted loop playsInline preload="metadata" /> : clip.thumbnail_url ? <img src={clip.thumbnail_url} alt={`${clip.title} önizlemesi`} /> : <div className="clip-card__placeholder"><Film size={30} /><span>Önizleme</span></div>}
        <span className="rank-badge">#{rank}</span>
        <span className="duration-badge"><Play size={11} fill="currentColor" /> {formatDuration(clip.duration)}</span>
        <ScoreRing score={clip.score} />
        {rendering && <span className="render-overlay"><LoaderCircle className="spin" size={18} /> Hazırlanıyor</span>}
      </div>
      <div className="clip-card__body">
        <span className="clip-card__time">{formatDuration(clip.start_time)} — {formatDuration(clip.end_time)} · {clip.aspect_ratio || '9:16'}</span>
        <h3>{clip.title}</h3>
        <div className="reason-chips">{reasons.map((reason) => <span key={reason}><Flame size={12} /> {reason}</span>)}</div>
        {breakdown.length > 0 && (
          <details className="score-details">
            <summary>Puanı neden yüksek? <ChevronDown size={15} /></summary>
            <div>{breakdown.slice(0, 5).map(([key, value]) => <span key={key}><small>{scoreLabel(key)}</small><i><b style={{ width: `${normalizeScore(value)}%` }} /></i><strong>{normalizeScore(value)}</strong></span>)}</div>
            {clip.scores.trend == null && <p className="score-details__note">Gündem puanı yok · canlı internet trendi kullanılmadı.</p>}
          </details>
        )}
      </div>
      <footer className="clip-card__footer">
        <button className="button button--primary" onClick={onEdit}><Edit3 size={16} /> Düzenle</button>
        {clip.download_url && clip.render_status === 'ready' ? (
          <a className="button button--secondary" href={clip.download_url} download><Download size={16} /> İndir</a>
        ) : (
          <button className="button button--secondary" onClick={onRender} disabled={rendering}>{rendering ? <LoaderCircle className="spin" size={16} /> : <Download size={16} />} {rendering ? 'Hazırlanıyor' : 'Hazırla'}</button>
        )}
      </footer>
    </article>
  )
}

function scoreLabel(key: string): string {
  const labels: Record<string, string> = { hook: 'Giriş', flow: 'Akış', value: 'Değer', trend: 'Gündem', safety: 'Güvenlik', visual: 'Görsel' }
  return labels[key.toLowerCase()] ?? key
}
