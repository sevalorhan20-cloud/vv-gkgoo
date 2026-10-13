import {
  ArrowRight,
  Clock3,
  Clapperboard,
  Film,
  FolderOpen,
  HardDrive,
  MoreHorizontal,
  Play,
  Plus,
  Sparkles,
  Trash2,
  UploadCloud,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { deleteProject, getProjects, getStats } from '../api'
import { EmptyState, ErrorState, LoadingState, StatusPill } from '../components/Common'
import { useToast } from '../components/Toast'
import type { Project, Stats } from '../types'
import { formatBytes, formatDate, formatDuration, isProjectActive } from '../utils'

interface DashboardProps {
  navigate: (path: string) => void
}

export function Dashboard({ navigate }: DashboardProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [menuId, setMenuId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const { notify } = useToast()

  const load = useCallback(async () => {
    setError(null)
    try {
      const [nextProjects, nextStats] = await Promise.all([getProjects(), getStats()])
      setProjects(nextProjects)
      setStats(nextStats)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Yerel sunucuya ulaşılamadı.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 10000)
    return () => window.clearInterval(timer)
  }, [load])

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuId(null)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const activeProjects = useMemo(() => projects.filter((project) => isProjectActive(project.status)), [projects])

  const handleDelete = async (project: Project) => {
    setMenuId(null)
    if (!window.confirm(`“${project.name}” projesi ve üretilen dosyaları silinsin mi?`)) return
    try {
      await deleteProject(project.id)
      setProjects((current) => current.filter((item) => item.id !== project.id))
      notify({ kind: 'success', title: 'Proje silindi', description: project.name })
      void getStats().then(setStats).catch(() => undefined)
    } catch (err) {
      notify({ kind: 'error', title: 'Proje silinemedi', description: err instanceof Error ? err.message : undefined })
    }
  }

  return (
    <div className="page dashboard-page">
      <section className="hero-card">
        <div className="hero-card__content">
          <span className="eyebrow"><Sparkles size={14} /> Yerel video zekâsı</span>
          <h1>Uzun videodan<br /><span>paylaşmaya hazır</span> anlar.</h1>
          <p>En güçlü bölümleri bul, dikey formata dönüştür ve altyazılarını hazırla. Videon cihazından hiç çıkmaz.</p>
          <div className="hero-card__actions">
            <button className="button button--primary button--large" onClick={() => navigate('/new')}>
              <Plus size={18} /> Yeni proje
            </button>
            <button className="button button--ghost button--large" onClick={() => document.getElementById('recent-projects')?.scrollIntoView({ behavior: 'smooth' })}>
              Projeleri gör <ArrowRight size={17} />
            </button>
          </div>
          <div className="hero-card__trust"><span><i /> Çevrimdışı çalışır</span><span><i /> Filigran yok</span></div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="hero-visual__glow" />
          <div className="frame frame--back"><span>00:18</span></div>
          <div className="frame frame--main">
            <div className="frame__top"><span className="frame__score">92</span><span>Güçlü giriş</span></div>
            <div className="frame__subject"><span className="frame__face" /></div>
            <div className="frame__caption">FİKRİNİZİ <em>DEĞİŞTİRECEK</em><br />TEK ŞEY BU.</div>
            <div className="frame__play"><Play size={17} fill="currentColor" /></div>
          </div>
          <div className="waveform">
            {[18, 35, 24, 52, 30, 64, 42, 72, 34, 57, 23, 69, 45, 32, 60, 28, 46, 20].map((height, index) => (
              <i style={{ height }} key={index} />
            ))}
          </div>
        </div>
      </section>

      <section className="metrics-grid" aria-label="Çalışma alanı özeti">
        <MetricCard icon={<Clapperboard />} label="Toplam proje" value={stats?.total_projects ?? 0} loading={loading} />
        <MetricCard icon={<Film />} label="Hazır klip" value={stats?.ready_clips ?? stats?.total_clips ?? 0} loading={loading} accent />
        <MetricCard icon={<Clock3 />} label="Devam eden" value={activeProjects.length} loading={loading} />
        <MetricCard
          icon={<HardDrive />}
          label="Yerel depolama"
          value={stats?.storage_bytes ? formatBytes(stats.storage_bytes) : '—'}
          loading={loading}
        />
      </section>

      {activeProjects.length > 0 && (
        <section className="section-block">
          <div className="section-heading">
            <div><span className="eyebrow eyebrow--muted">Canlı işler</span><h2>İşlem devam ediyor</h2></div>
          </div>
          <div className="active-jobs">
            {activeProjects.map((project) => (
              <button className="active-job" onClick={() => navigate(`/projects/${project.id}`)} key={project.id}>
                <span className="active-job__thumb"><Film size={21} /></span>
                <span className="active-job__info"><strong>{project.name}</strong><small>{project.message || 'Video analiz ediliyor…'}</small></span>
                <span className="active-job__meter"><i style={{ width: `${project.progress}%` }} /></span>
                <strong className="active-job__percent">%{project.progress}</strong>
                <ArrowRight size={17} />
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="section-block" id="recent-projects">
        <div className="section-heading">
          <div><span className="eyebrow eyebrow--muted">Kütüphane</span><h2>Son projeler</h2></div>
          {projects.length > 0 && <button className="text-button" onClick={() => navigate('/library')}>Tümünü gör <ArrowRight size={15} /></button>}
        </div>

        {loading && projects.length === 0 ? (
          <LoadingState label="Projeler yükleniyor…" />
        ) : error && projects.length === 0 ? (
          <ErrorState message={error} onRetry={() => void load()} />
        ) : projects.length === 0 ? (
          <EmptyState
            icon={<UploadCloud size={25} />}
            title="İlk projenizi oluşturun"
            description="Bir video seçin; KlipForge en güçlü anları tamamen bu cihazda bulsun."
            action={<button className="button button--primary" onClick={() => navigate('/new')}><Plus size={17} /> Video seç</button>}
          />
        ) : (
          <div className="project-list">
            <div className="project-list__head" aria-hidden="true">
              <span>Proje</span><span>Durum</span><span>Klip</span><span>Son düzenleme</span><span />
            </div>
            {projects.slice(0, 8).map((project) => (
              <div className="project-row" key={project.id}>
                <button className="project-row__main" onClick={() => navigate(`/projects/${project.id}`)}>
                  <span className="project-thumb">
                    {project.thumbnail_url ? <img src={project.thumbnail_url} alt="" /> : <Film size={20} />}
                    {project.duration ? <small>{formatDuration(project.duration)}</small> : null}
                  </span>
                  <span className="project-name"><strong>{project.name}</strong><small>{project.file_size ? formatBytes(project.file_size) : 'Yerel video'}</small></span>
                </button>
                <StatusPill status={project.status} progress={project.progress} />
                <span className="project-row__clips">{project.clips.length}</span>
                <span className="project-row__date">{formatDate(project.updated_at ?? project.created_at)}</span>
                <div className="project-menu" ref={menuId === project.id ? menuRef : undefined}>
                  <button className="icon-button" onClick={() => setMenuId(menuId === project.id ? null : project.id)} aria-label={`${project.name} seçenekleri`} aria-expanded={menuId === project.id}>
                    <MoreHorizontal size={19} />
                  </button>
                  {menuId === project.id && (
                    <div className="dropdown-menu">
                      <button onClick={() => navigate(`/projects/${project.id}`)}><FolderOpen size={16} /> Aç</button>
                      <button className="dropdown-menu__danger" onClick={() => void handleDelete(project)}><Trash2 size={16} /> Sil</button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function MetricCard({
  icon,
  label,
  value,
  loading,
  accent,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  loading: boolean
  accent?: boolean
}) {
  return (
    <div className={`metric-card ${accent ? 'metric-card--accent' : ''}`}>
      <span className="metric-card__icon">{icon}</span>
      <div><span>{label}</span>{loading ? <i className="skeleton skeleton--number" /> : <strong>{value}</strong>}</div>
    </div>
  )
}
