import { useCallback, useEffect, useRef, useState } from 'react'
import { getHealth } from './api'
import { Shell, type RouteInfo } from './components/Shell'
import type { HealthResponse } from './types'
import { Dashboard } from './views/Dashboard'
import { Editor } from './views/Editor'
import { Library } from './views/Library'
import { Project } from './views/Project'
import { Settings } from './views/Settings'
import { Upload } from './views/Upload'

function parseRoute(pathname: string): RouteInfo {
  const parts = pathname.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean)
  if (parts.length === 0) return { page: 'dashboard' }
  if (parts[0] === 'new') return { page: 'upload' }
  if (parts[0] === 'library') return { page: 'library' }
  if (parts[0] === 'settings') return { page: 'settings' }
  if (parts[0] === 'projects' && parts[1] && parts[2] === 'clips' && parts[3] && parts[4] === 'edit') {
    return { page: 'editor', projectId: decodeURIComponent(parts[1]), clipId: decodeURIComponent(parts[3]) }
  }
  if (parts[0] === 'projects' && parts[1]) return { page: 'project', projectId: decodeURIComponent(parts[1]) }
  return { page: 'dashboard' }
}

export default function App() {
  const [route, setRoute] = useState<RouteInfo>(() => parseRoute(window.location.pathname))
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState(false)
  const editorDirtyRef = useRef(false)
  const currentPathRef = useRef(window.location.pathname)

  const setEditorDirty = useCallback((dirty: boolean) => {
    editorDirtyRef.current = dirty
  }, [])

  const confirmDiscard = useCallback(() => (
    !editorDirtyRef.current
    || window.confirm('Kaydedilmemiş değişiklikleriniz var. Bu sayfadan ayrılmak istediğinize emin misiniz?')
  ), [])

  const navigate = useCallback((path: string) => {
    if (window.location.pathname !== path) {
      if (!confirmDiscard()) return
      editorDirtyRef.current = false
      window.history.pushState({}, '', path)
      currentPathRef.current = path
    }
    setRoute(parseRoute(path))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [confirmDiscard])

  useEffect(() => {
    const onPopState = () => {
      const nextPath = window.location.pathname
      const previousPath = currentPathRef.current
      if (nextPath !== previousPath && !confirmDiscard()) {
        window.history.pushState({}, '', previousPath)
        return
      }
      editorDirtyRef.current = false
      currentPathRef.current = nextPath
      setRoute(parseRoute(nextPath))
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [confirmDiscard])

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!editorDirtyRef.current) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [])

  useEffect(() => {
    let mounted = true
    const check = async () => {
      try {
        const next = await getHealth()
        if (mounted) {
          setHealth(next)
          setHealthError(false)
        }
      } catch {
        if (mounted) setHealthError(true)
      }
    }
    void check()
    const timer = window.setInterval(() => void check(), 15000)
    return () => {
      mounted = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      if (target.matches('input, textarea, select, [contenteditable="true"]')) return
      if (event.key.toLowerCase() === 'n' && route.page !== 'editor') navigate('/new')
    }
    window.addEventListener('keydown', onShortcut)
    return () => window.removeEventListener('keydown', onShortcut)
  }, [navigate, route.page])

  return (
    <Shell route={route} navigate={navigate} health={health} healthError={healthError}>
      {route.page === 'dashboard' && <Dashboard navigate={navigate} />}
      {route.page === 'upload' && <Upload navigate={navigate} />}
      {route.page === 'project' && route.projectId && <Project projectId={route.projectId} navigate={navigate} />}
      {route.page === 'editor' && route.projectId && route.clipId && <Editor projectId={route.projectId} clipId={route.clipId} navigate={navigate} onDirtyChange={setEditorDirty} />}
      {route.page === 'library' && <Library navigate={navigate} />}
      {route.page === 'settings' && <Settings health={health} healthError={healthError} />}
    </Shell>
  )
}
