import { CheckCircle2, Cpu, Database, HardDrive, MonitorCog, ShieldCheck, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import type { HealthResponse } from '../types'
import { formatBytes } from '../utils'

export function Settings({ health, healthError }: { health: HealthResponse | null; healthError: boolean }) {
  const engine = (health?.engine && typeof health.engine === 'object' ? health.engine : {}) as Record<string, unknown>
  const system = (health?.system && typeof health.system === 'object' ? health.system : {}) as Record<string, unknown>
  const transcription = (engine.transcription && typeof engine.transcription === 'object' ? engine.transcription : {}) as Record<string, unknown>
  const faceTracking = (engine.face_tracking && typeof engine.face_tracking === 'object' ? engine.face_tracking : {}) as Record<string, unknown>
  const maxUpload = typeof system.max_upload_bytes === 'number' ? system.max_upload_bytes : undefined
  const diskFree = typeof system.disk_free === 'number' ? system.disk_free : undefined

  return (
    <div className="page settings-page">
      <div className="page-header">
        <span className="eyebrow"><MonitorCog size={14} /> Yerel sistem</span>
        <h1>Ayarlar ve durum</h1>
        <p>KlipForge motorunun bu cihazdaki yeteneklerini görüntüleyin.</p>
      </div>
      <section className={`system-banner ${healthError ? 'system-banner--error' : ''}`}>
        <span>{healthError ? <TriangleAlert size={24} /> : <CheckCircle2 size={24} />}</span>
        <div>
          <h2>{healthError ? 'Yerel motora ulaşılamıyor' : health?.status === 'degraded' ? 'Motor sınırlı çalışıyor' : 'Yerel motor hazır'}</h2>
          <p>{healthError ? 'Backend servisinin çalıştığını ve port ayarını kontrol edin.' : `KlipForge ${health?.version ? `v${health.version}` : ''} · Telemetri kapalı`}</p>
        </div>
      </section>
      <div className="settings-grid">
        <CapabilityCard icon={<Cpu />} title="Video motoru" items={[['FFmpeg', Boolean(engine.ffmpeg)], ['FFprobe', Boolean(engine.ffprobe)], ['Yüz odak tespiti', Boolean(faceTracking.available)]]} />
        <CapabilityCard icon={<ShieldCheck />} title="Gizlilik" items={[['Yalnızca yerel', health?.local_only === true], ['Telemetri kapalı', health?.telemetry === false], ['Harici yükleme yok', health?.local_only === true]]} />
        <div className="settings-card">
          <div className="settings-card__heading"><span><HardDrive size={19} /></span><div><h2>Depolama</h2><p>Sunucunun bildirdiği sınırlar</p></div></div>
          <dl className="settings-data"><div><dt>Boş alan</dt><dd>{formatBytes(diskFree)}</dd></div><div><dt>Tek video sınırı</dt><dd>{formatBytes(maxUpload)}</dd></div><div><dt>Platform</dt><dd>{String(system.platform ?? '—')}</dd></div></dl>
        </div>
        <div className="settings-card">
          <div className="settings-card__heading"><span><Database size={19} /></span><div><h2>Konuşma modeli</h2><p>Yerel transkripsiyon yeteneği</p></div></div>
          <dl className="settings-data"><div><dt>Durum</dt><dd>{transcription.available ? 'Hazır' : 'Kullanılamıyor'}</dd></div><div><dt>Motor</dt><dd>{String(transcription.engine ?? transcription.model ?? '—')}</dd></div><div><dt>CPU iş parçacığı</dt><dd>{String(system.cpu_threads ?? '—')}</dd></div></dl>
        </div>
      </div>
      <div className="privacy-detail"><ShieldCheck size={21} /><div><h2>Dosyalarınız cihazınızda kalır</h2><p>Arayüz yalnızca aynı makinedeki KlipForge API’siyle konuşur. Sağlık yanıtına göre telemetri kapalıdır ve medya üçüncü taraf servislere yüklenmez.</p></div></div>
    </div>
  )
}

function CapabilityCard({ icon, title, items }: { icon: ReactNode; title: string; items: Array<[string, boolean]> }) {
  return (
    <div className="settings-card">
      <div className="settings-card__heading"><span>{icon}</span><div><h2>{title}</h2><p>Canlı motor durumu</p></div></div>
      <div className="capability-list">{items.map(([label, available]) => <span key={label}><i className={available ? 'available' : ''}>{available ? '✓' : '!'}</i>{label}<strong>{available ? 'Hazır' : 'Eksik'}</strong></span>)}</div>
    </div>
  )
}
