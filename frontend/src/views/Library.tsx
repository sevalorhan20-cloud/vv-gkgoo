import { ArrowRight, Captions, Download, Film, FolderOpen, Search, Sparkles, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { getProjects } from '../api'
import { EmptyState, ErrorState, LoadingState, ScoreRing } from '../components/Common'
import type { Clip, Project } from '../types'
import { formatDuration } from '../utils'

export function Library({ navigate }: { navigate: (path: string) => void }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [readyOnly, setReadyOnly] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      setProjects(await getProjects())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Klip kütüphanesi yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const clips = useMemo(
    () => projects
      .flatMap((project) => project.clips.map((clip) => ({ clip, project })))
      .filter(({ clip, project }) => {
        const needle = query.toLocaleLowerCase('tr-TR')
        const matches = clip.title.toLocaleLowerCase('tr-TR').includes(needle)
          || project.name.toLocaleLowerCase('tr-TR').includes(needle)
        return matches && (!readyOnly || clip.render_status === 'ready')
      })
      .sort((a, b) => b.clip.score - a.clip.score),
    [projects, query, readyOnly],
  )

  return (
    <div className="page library-page">
      <div className="page-header page-header--split">
        <div>
          <span className="eyebrow"><FolderOpen size={14} /> Yerel kütüphane</span>
          <h1>Tüm klipler</h1>
          <p>Projelerinizde bulunan anları tek yerden inceleyin.</p>
        </div>
        <button className="button button--primary" onClick={() => navigate('/new')}><Sparkles size={17} /> Yeni analiz</button>
      </div>
      <div className="library-toolbar">
        <label className="search-field">
          <Search size={17} /><span className="sr-only">Klip ara</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Başlık veya proje ara…" />
          {query && <button onClick={() => setQuery('')} aria-label="Aramayı temizle"><X size={15} /></button>}
        </label>
        <label className="check-filter"><input type="checkbox" checked={readyOnly} onChange={(event) => setReadyOnly(event.target.checked)} /><i /> Yalnız indirilmeye hazır</label>
        <span className="results-count">{clips.length} klip</span>
      </div>
      {loading ? (
        <LoadingState label="Klipler yükleniyor…" />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : projects.length === 0 ? (
        <EmptyState icon={<Film size={25} />} title="Henüz klip yok" description="İlk videonuzu analiz ettiğinizde seçilen anlar burada görünecek." action={<button className="button button--primary" onClick={() => navigate('/new')}>Video seç</button>} />
      ) : clips.length === 0 ? (
        <EmptyState icon={<Search size={24} />} title="Eşleşen klip yok" description="Arama metnini veya filtreyi değiştirin." action={<button className="button button--secondary" onClick={() => { setQuery(''); setReadyOnly(false) }}>Filtreleri temizle</button>} />
      ) : (
        <div className="library-grid">
          {clips.map(({ clip, project }) => <LibraryCard key={`${project.id}-${clip.id}`} clip={clip} project={project} navigate={navigate} />)}
        </div>
      )}
    </div>
  )
}

function LibraryCard({ clip, project, navigate }: { clip: Clip; project: Project; navigate: (path: string) => void }) {
  return (
    <article className="library-card">
      <button className="library-card__preview" onClick={() => navigate(`/projects/${project.id}/clips/${clip.id}/edit`)}>
        {clip.thumbnail_url ? <img src={clip.thumbnail_url} alt="" /> : <span><Film size={27} /></span>}
        <ScoreRing score={clip.score} size="small" />
        <small>{formatDuration(clip.duration)}</small>
      </button>
      <div className="library-card__content">
        <span>{project.name}</span><h2>{clip.title}</h2>
        <div><span><Captions size={13} /> {clip.caption_preset ?? 'impact'}</span><span>{clip.aspect_ratio ?? '9:16'}</span></div>
      </div>
      <footer>
        <button className="text-button" onClick={() => navigate(`/projects/${project.id}/clips/${clip.id}/edit`)}>Düzenle <ArrowRight size={14} /></button>
        {clip.download_url && clip.render_status === 'ready' && <a className="icon-button" href={clip.download_url} download aria-label={`${clip.title} klibini indir`}><Download size={17} /></a>}
      </footer>
    </article>
  )
}
