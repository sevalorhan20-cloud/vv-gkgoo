import {
  Activity,
  ChevronRight,
  CircleHelp,
  Film,
  FolderOpen,
  Gauge,
  Menu,
  Plus,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { getProjects } from '../api'
import type { HealthResponse, Project } from '../types'
import { getProjectStatusLabel, isProjectActive } from '../utils'
import { BrandMark } from './Common'

export interface RouteInfo {
  page: 'dashboard' | 'upload' | 'project' | 'editor' | 'library' | 'settings'
  projectId?: string
  clipId?: string
}

interface ShellProps {
  children: ReactNode
  route: RouteInfo
  navigate: (path: string) => void
  health: HealthResponse | null
  healthError: boolean
}

const navItems = [
  { page: 'dashboard', label: 'Ana Sayfa', icon: Gauge, path: '/' },
  { page: 'upload', label: 'Yeni Proje', icon: Plus, path: '/new' },
  { page: 'library', label: 'Klipler', icon: Film, path: '/library' },
] as const

export function Shell({ children, route, navigate, health, healthError }: ShellProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [mobileViewport, setMobileViewport] = useState(() => window.matchMedia('(max-width: 768px)').matches)
  const [activeProject, setActiveProject] = useState<Project | null>(null)

  useEffect(() => {
    const query = window.matchMedia('(max-width: 768px)')
    const updateViewport = (event: MediaQueryListEvent) => setMobileViewport(event.matches)
    setMobileViewport(query.matches)
    query.addEventListener('change', updateViewport)
    return () => query.removeEventListener('change', updateViewport)
  }, [])

  useEffect(() => {
    let mounted = true
    let timer: number | undefined

    const refresh = async () => {
      try {
        const projects = await getProjects()
        if (mounted) setActiveProject(projects.find((project) => isProjectActive(project.status)) ?? null)
      } catch {
        if (mounted) setActiveProject(null)
      } finally {
        if (mounted) timer = window.setTimeout(refresh, 8000)
      }
    }
    void refresh()
    return () => {
      mounted = false
      if (timer) window.clearTimeout(timer)
    }
  }, [route.page])

  const healthLabel = useMemo(() => {
    if (healthError) return 'Motor çevrimdışı'
    if (!health) return 'Motor denetleniyor'
    if (health.ready === false || health.status === 'error') return 'Motor hazırlanıyor'
    return 'Yerel motor hazır'
  }, [health, healthError])

  const currentTitle =
    route.page === 'dashboard'
      ? 'Ana Sayfa'
      : route.page === 'upload'
        ? 'Yeni Proje'
        : route.page === 'editor'
          ? 'Klip Editörü'
          : route.page === 'library'
            ? 'Klipler'
            : route.page === 'settings'
              ? 'Ayarlar'
              : 'Proje'

  const go = (path: string) => {
    setMenuOpen(false)
    navigate(path)
  }

  return (
    <div className={`app-shell ${route.page === 'editor' ? 'app-shell--editor' : ''}`}>
      <a className="skip-link" href="#main-content">Ana içeriğe geç</a>

      <aside
        className={`sidebar ${menuOpen ? 'sidebar--open' : ''}`}
        aria-label="Ana menü"
        aria-hidden={mobileViewport && !menuOpen ? true : undefined}
        inert={mobileViewport && !menuOpen ? true : undefined}
      >
        <button className="sidebar__close icon-button" onClick={() => setMenuOpen(false)} aria-label="Menüyü kapat">
          <X size={20} />
        </button>
        <button className="sidebar__brand" onClick={() => go('/')} aria-label="KlipForge ana sayfa">
          <BrandMark />
        </button>

        <nav className="sidebar__nav">
          <span className="sidebar__label">Çalışma alanı</span>
          {navItems.map((item) => {
            const Icon = item.icon
            const active = route.page === item.page
            return (
              <button className={`nav-item ${active ? 'nav-item--active' : ''}`} onClick={() => go(item.path)} key={item.page}>
                <Icon size={19} aria-hidden="true" />
                <span>{item.label}</span>
                {item.page === 'upload' && <span className="nav-item__key">N</span>}
              </button>
            )
          })}

          <span className="sidebar__label sidebar__label--spaced">Sistem</span>
          <button className={`nav-item ${route.page === 'settings' ? 'nav-item--active' : ''}`} onClick={() => go('/settings')}>
            <Settings size={19} aria-hidden="true" />
            <span>Ayarlar</span>
          </button>
          <a className="nav-item" href="/api/docs" target="_blank" rel="noreferrer">
            <CircleHelp size={19} aria-hidden="true" />
            <span>API Yardımı</span>
          </a>
        </nav>

        <div className="privacy-card">
          <ShieldCheck size={19} aria-hidden="true" />
          <div>
            <strong>%100 yerel</strong>
            <span>Videolar bu cihazdan çıkmaz.</span>
          </div>
        </div>
      </aside>

      {menuOpen && <button className="sidebar-backdrop" onClick={() => setMenuOpen(false)} aria-label="Menüyü kapat" />}

      <header className="topbar">
        <div className="topbar__left">
          <button className="menu-button icon-button" onClick={() => setMenuOpen(true)} aria-label="Menüyü aç">
            <Menu size={21} />
          </button>
          <div className="topbar__brand-mobile"><BrandMark compact /></div>
          <div className="breadcrumb" aria-label="Sayfa yolu">
            <span>KlipForge</span>
            <ChevronRight size={14} aria-hidden="true" />
            <strong>{currentTitle}</strong>
          </div>
        </div>
        <div className="topbar__actions">
          <div className={`engine-status ${healthError ? 'engine-status--offline' : ''}`} title={health?.device ?? undefined}>
            <span className="engine-status__dot" aria-hidden="true" />
            <span>{healthLabel}</span>
          </div>
          <button className="icon-button topbar__tune" aria-label="Sistem ayarlarını aç" onClick={() => go('/settings')}>
            <SlidersHorizontal size={18} />
          </button>
          <button className="avatar" aria-label="Yerel sistem ayarları" onClick={() => go('/settings')}>KF</button>
        </div>
      </header>

      <main id="main-content" className="main-content" tabIndex={-1}>{children}</main>

      <nav className="mobile-nav" aria-label="Mobil ana menü">
        <button className={route.page === 'dashboard' ? 'active' : ''} onClick={() => go('/')}>
          <Gauge size={20} /><span>Ana Sayfa</span>
        </button>
        <button className={route.page === 'library' ? 'active' : ''} onClick={() => go('/library')}>
          <FolderOpen size={20} /><span>Klipler</span>
        </button>
        <button className="mobile-nav__create" onClick={() => go('/new')} aria-label="Yeni proje">
          <Plus size={24} />
        </button>
        <button className={route.page === 'project' ? 'active' : ''} onClick={() => activeProject && go(`/projects/${activeProject.id}`)} disabled={!activeProject}>
          <Activity size={20} /><span>İşlem</span>
        </button>
        <button className={route.page === 'settings' ? 'active' : ''} onClick={() => go('/settings')}>
          <Settings size={20} /><span>Ayarlar</span>
        </button>
      </nav>

      {activeProject && route.projectId !== activeProject.id && (
        <button className="job-mini" onClick={() => go(`/projects/${activeProject.id}`)}>
          <span className="job-mini__icon"><Sparkles size={17} /></span>
          <span className="job-mini__content">
            <strong>{activeProject.name}</strong>
            <span>{getProjectStatusLabel(activeProject.status)} · %{activeProject.progress}</span>
          </span>
          <span className="job-mini__progress" aria-hidden="true"><i style={{ width: `${activeProject.progress}%` }} /></span>
          <ChevronRight size={17} />
        </button>
      )}
    </div>
  )
}
