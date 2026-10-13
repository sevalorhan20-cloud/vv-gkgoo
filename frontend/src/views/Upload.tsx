import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Cpu,
  FileVideo,
  Film,
  Gamepad2,
  GraduationCap,
  LoaderCircle,
  LockKeyhole,
  Mic2,
  MonitorPlay,
  Sparkles,
  UploadCloud,
  X,
  Zap,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { createProject } from '../api'
import { useToast } from '../components/Toast'
import type { AspectRatio, CaptionPreset, ProjectGoal, ProjectSettings } from '../types'
import { formatBytes, formatDuration } from '../utils'

interface UploadProps {
  navigate: (path: string) => void
}

const initialSettings: ProjectSettings = {
  goal: 'viral',
  aspect_ratio: '9:16',
  min_duration: 15,
  max_duration: 60,
  language: 'auto',
  clip_count: 5,
  caption_preset: 'impact',
  enable_captions: true,
  auto_reframe: true,
  remove_silence: false,
  prompt: '',
  min_score: 0,
  scene_sensitivity: 0.3,
}

const goals: Array<{ id: ProjectGoal; label: string; description: string; icon: typeof Zap }> = [
  { id: 'viral', label: 'Öne çıkan anlar', description: 'Güçlü giriş ve yüksek tempo', icon: Zap },
  { id: 'education', label: 'Bilgi & öğreti', description: 'Net çıkarımlar ve faydalı bilgi', icon: GraduationCap },
  { id: 'podcast', label: 'Podcast kesitleri', description: 'Bağlamlı konuşma bölümleri', icon: Mic2 },
  { id: 'gaming', label: 'Oyun & aksiyon', description: 'Tepkiler ve yüksek enerji', icon: Gamepad2 },
  { id: 'custom', label: 'Dengeli analiz', description: 'Tüm sinyaller dengeli', icon: Sparkles },
]

const captionPresets: Array<{ id: CaptionPreset; label: string; sample: string }> = [
  { id: 'impact', label: 'Vurgu', sample: 'BUNU bilmen gerek' },
  { id: 'minimal', label: 'Minimal', sample: 'Bunu bilmen gerek' },
  { id: 'boxed', label: 'Kutulu', sample: 'Bunu bilmen gerek' },
  { id: 'clean', label: 'Temiz', sample: 'Bunu bilmen gerek' },
]

export function Upload({ navigate }: UploadProps) {
  const [step, setStep] = useState(1)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [metadata, setMetadata] = useState<{ duration?: number; width?: number; height?: number }>({})
  const [settings, setSettings] = useState<ProjectSettings>(initialSettings)
  const [dragging, setDragging] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const { notify } = useToast()

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  const updateSettings = <K extends keyof ProjectSettings>(key: K, value: ProjectSettings[K]) => {
    setSettings((current) => ({ ...current, [key]: value }))
  }

  const chooseFile = (selected?: File) => {
    if (!selected) return
    const extension = selected.name.split('.').pop()?.toLowerCase()
    if (!selected.type.startsWith('video/') && !['mp4', 'mov', 'webm', 'mkv', 'm4v', 'avi', 'mpg', 'mpeg'].includes(extension ?? '')) {
      notify({ kind: 'error', title: 'Desteklenmeyen dosya', description: 'MP4, MOV, WebM, MKV, M4V, AVI veya MPEG video seçin.' })
      return
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    const url = URL.createObjectURL(selected)
    setFile(selected)
    setPreviewUrl(url)
    setMetadata({})
  }

  const clearFile = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
    setFile(null)
    setMetadata({})
    if (inputRef.current) inputRef.current.value = ''
  }

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    chooseFile(event.dataTransfer.files[0])
  }

  const canContinue = step === 1 ? Boolean(file) : true

  const submit = async () => {
    if (!file) return
    setSubmitting(true)
    setUploadProgress(0)
    try {
      const project = await createProject(file, settings, setUploadProgress)
      notify({ kind: 'success', title: 'Analiz başlatıldı', description: 'Videonuz yerel motor tarafından işleniyor.' })
      navigate(`/projects/${project.id}`)
    } catch (err) {
      notify({ kind: 'error', title: 'Proje oluşturulamadı', description: err instanceof Error ? err.message : 'Yerel sunucuya ulaşılamadı.' })
      setSubmitting(false)
    }
  }

  const estimated = useMemo(() => {
    if (!metadata.duration) return 'Video bilgisi alındığında hesaplanır'
    const minutes = Math.max(1, Math.ceil(metadata.duration / 60))
    return `Yaklaşık ${Math.max(1, Math.ceil(minutes * 0.35))}–${Math.max(2, Math.ceil(minutes * 0.9))} dk`
  }, [metadata.duration])

  return (
    <div className="page upload-page">
      <div className="page-header page-header--centered">
        <button className="back-button" onClick={() => navigate('/')}><ArrowLeft size={17} /> Ana sayfa</button>
        <span className="eyebrow"><Sparkles size={14} /> Yeni yerel analiz</span>
        <h1>Yeni proje oluştur</h1>
        <p>Kaynağınızı seçin, hedefi belirleyin ve gerisini KlipForge’a bırakın.</p>
      </div>

      <ol className="stepper" aria-label="Proje oluşturma adımları">
        {[
          ['Kaynak', 'Videoyu seç'],
          ['Hedef', 'Klipleri ayarla'],
          ['Analiz', 'Kontrol et'],
        ].map(([title, detail], index) => {
          const number = index + 1
          const active = step === number
          const done = step > number
          return (
            <li className={`${active ? 'active' : ''} ${done ? 'done' : ''}`} key={title} aria-current={active ? 'step' : undefined}>
              <span className="stepper__number">{done ? <Check size={15} /> : number}</span>
              <span><strong>{title}</strong><small>{detail}</small></span>
            </li>
          )
        })}
      </ol>

      <section className="wizard-card">
        {step === 1 && (
          <div className="wizard-section">
            <div className="wizard-section__heading">
              <span className="number-tag">01</span>
              <div><h2>Kaynak videoyu seçin</h2><p>Video yalnızca bu cihazdaki KlipForge sunucusuna gönderilir.</p></div>
            </div>

            {!file ? (
              <div
                className={`dropzone ${dragging ? 'dropzone--active' : ''}`}
                onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false) }}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
                onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click() }}
                role="button"
                tabIndex={0}
              >
                <input ref={inputRef} type="file" accept="video/*,.mkv,.m4v,.avi,.mpg,.mpeg" onChange={(event) => chooseFile(event.target.files?.[0])} hidden />
                <span className="dropzone__icon"><UploadCloud size={29} /></span>
                <h3>{dragging ? 'Videoyu buraya bırakın' : 'Videonuzu sürükleyip bırakın'}</h3>
                <p>veya cihazınızdan bir dosya seçin</p>
                <button className="button button--secondary" type="button">Video seç</button>
                <small>MP4, MOV, WebM, MKV, AVI, MPEG · Sınır, yerel sunucu yapılandırmanıza bağlıdır</small>
              </div>
            ) : (
              <div className="file-preview">
                <div className="file-preview__media">
                  {previewUrl && (
                    <video
                      src={previewUrl}
                      controls
                      preload="metadata"
                      onLoadedMetadata={(event) => {
                        const video = event.currentTarget
                        setMetadata({ duration: video.duration, width: video.videoWidth, height: video.videoHeight })
                      }}
                    />
                  )}
                </div>
                <div className="file-preview__details">
                  <span className="file-preview__icon"><FileVideo size={23} /></span>
                  <div><strong>{file.name}</strong><span>{formatBytes(file.size)}{metadata.duration ? ` · ${formatDuration(metadata.duration)}` : ''}{metadata.width ? ` · ${metadata.width}×${metadata.height}` : ''}</span></div>
                  <button className="icon-button" onClick={clearFile} aria-label="Videoyu kaldır"><X size={19} /></button>
                </div>
                <div className="local-notice"><LockKeyhole size={16} /><span><strong>Cihazında kalır.</strong> Dosyan dış servislere gönderilmez.</span></div>
              </div>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="wizard-section">
            <div className="wizard-section__heading">
              <span className="number-tag">02</span>
              <div><h2>Klip hedefini belirleyin</h2><p>Analizin neye odaklanacağını ve çıktı biçimini seçin.</p></div>
            </div>

            <fieldset className="form-group">
              <legend>İçerik hedefi</legend>
              <div className="goal-grid">
                {goals.map((goal) => {
                  const Icon = goal.icon
                  return (
                    <label className={`choice-card ${settings.goal === goal.id ? 'choice-card--selected' : ''}`} key={goal.id}>
                      <input type="radio" name="goal" value={goal.id} checked={settings.goal === goal.id} onChange={() => updateSettings('goal', goal.id)} />
                      <span className="choice-card__icon"><Icon size={19} /></span>
                      <span><strong>{goal.label}</strong><small>{goal.description}</small></span>
                      <CheckCircle2 className="choice-card__check" size={17} />
                    </label>
                  )
                })}
              </div>
            </fieldset>

            <div className="form-grid form-grid--three">
              <fieldset className="form-group">
                <legend>En-boy oranı</legend>
                <div className="segmented-control">
                  {(['9:16', '1:1', '16:9'] as AspectRatio[]).map((ratio) => (
                    <label className={settings.aspect_ratio === ratio ? 'selected' : ''} key={ratio}>
                      <input type="radio" name="ratio" checked={settings.aspect_ratio === ratio} onChange={() => updateSettings('aspect_ratio', ratio)} />
                      <span className={`ratio-icon ratio-icon--${ratio.replace(':', '-')}`} />{ratio}
                    </label>
                  ))}
                </div>
              </fieldset>

              <label className="form-group">
                <span className="label">Klip süresi</span>
                <select value={`${settings.min_duration}-${settings.max_duration}`} onChange={(event) => {
                  const [min, max] = event.target.value.split('-').map(Number)
                  setSettings((current) => ({ ...current, min_duration: min, max_duration: max }))
                }}>
                  <option value="15-30">15–30 saniye</option>
                  <option value="30-60">30–60 saniye</option>
                  <option value="15-60">15–60 saniye</option>
                  <option value="60-90">60–90 saniye</option>
                </select>
              </label>

              <label className="form-group">
                <span className="label">Klip sayısı</span>
                <select value={settings.clip_count} onChange={(event) => updateSettings('clip_count', Number(event.target.value))}>
                  <option value={3}>3 klip</option><option value={5}>5 klip</option><option value={10}>10 klip</option><option value={12}>12 klip</option>
                </select>
              </label>
            </div>

            <fieldset className="form-group">
              <legend>Altyazı stili</legend>
              <div className="caption-presets">
                {captionPresets.map((preset) => (
                  <label className={`caption-preset caption-preset--${preset.id} ${settings.caption_preset === preset.id ? 'selected' : ''}`} key={preset.id}>
                    <input type="radio" name="caption" checked={settings.caption_preset === preset.id} onChange={() => updateSettings('caption_preset', preset.id)} />
                    <span className="caption-preset__preview">{preset.sample}</span>
                    <strong>{preset.label}</strong>
                    <Check size={15} />
                  </label>
                ))}
              </div>
            </fieldset>

            <button className={`advanced-toggle ${advanced ? 'open' : ''}`} onClick={() => setAdvanced(!advanced)} aria-expanded={advanced}>
              <span><Cpu size={18} /> Gelişmiş analiz ayarları</span><ChevronDown size={18} />
            </button>
            {advanced && (
              <div className="advanced-panel">
                <label className="form-group"><span className="label">Konuşma dili</span><select value={settings.language} onChange={(event) => updateSettings('language', event.target.value)}><option value="auto">Otomatik algıla</option><option value="tr">Türkçe</option><option value="en">İngilizce</option><option value="de">Almanca</option><option value="es">İspanyolca</option></select></label>
                <Toggle label="Altyazıları etkinleştir" detail="Render sırasında konuşmayı videoya işle" checked={settings.enable_captions} onChange={(value) => updateSettings('enable_captions', value)} />
                <Toggle label="Otomatik kadraj" detail="Algılanan yüzlerin medyan konumuna göre sabit kırpma odağı seç" checked={settings.auto_reframe} onChange={(value) => updateSettings('auto_reframe', value)} />
                <div className="coming-soon-setting"><span><strong>Sessiz boşlukları azalt</strong><small>Doğal duraklamaları otomatik kısaltma</small></span><em>Yakında</em></div>
                <label className="form-group form-group--wide"><span className="label">Özel odak <small>(isteğe bağlı)</small></span><input type="text" maxLength={500} value={settings.prompt} onChange={(event) => updateSettings('prompt', event.target.value)} placeholder="Örn. özellikle ürün ipuçlarını ve net çıkarımları bul" /></label>
                <label className="form-group"><span className="label">Minimum puan · {settings.min_score}</span><input type="range" min={0} max={90} step={5} value={settings.min_score} onChange={(event) => updateSettings('min_score', Number(event.target.value))} /></label>
                <label className="form-group"><span className="label">Sahne hassasiyeti · %{Math.round(settings.scene_sensitivity * 100)}</span><input type="range" min={0.1} max={0.8} step={0.05} value={settings.scene_sensitivity} onChange={(event) => updateSettings('scene_sensitivity', Number(event.target.value))} /></label>
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="wizard-section review-section">
            <div className="wizard-section__heading">
              <span className="number-tag">03</span>
              <div><h2>Analize hazırsınız</h2><p>Ayarları kontrol edin. İşlem başladıktan sonra bu sayfadan ayrılabilirsiniz.</p></div>
            </div>
            <div className="review-grid">
              <div className="review-video">
                {previewUrl ? <video src={previewUrl} muted preload="metadata" /> : <Film size={35} />}
                <div><strong>{file?.name}</strong><span>{file ? formatBytes(file.size) : ''} · {metadata.duration ? formatDuration(metadata.duration) : 'Süre okunuyor'}</span></div>
              </div>
              <dl className="review-list">
                <div><dt>Hedef</dt><dd>{goals.find((goal) => goal.id === settings.goal)?.label}</dd></div>
                <div><dt>Çıktı</dt><dd>{settings.aspect_ratio} · {settings.min_duration}–{settings.max_duration} sn</dd></div>
                <div><dt>Klip sayısı</dt><dd>En fazla {settings.clip_count}</dd></div>
                <div><dt>Dil</dt><dd>{settings.language === 'auto' ? 'Otomatik algıla' : settings.language.toUpperCase()}</dd></div>
                <div><dt>Tahmini süre</dt><dd>{estimated}</dd></div>
              </dl>
            </div>
            <div className="analysis-notice">
              <span className="analysis-notice__icon"><LockKeyhole size={20} /></span>
              <div><strong>Gizlilik önce gelir</strong><p>Video, transkript ve oluşturulan klipler yalnızca yerel KlipForge sunucunuzda tutulur.</p></div>
            </div>
            {submitting && (
              <div className="upload-progress" role="status">
                <div><span><LoaderCircle className="spin" size={17} /> Video yerel motora aktarılıyor</span><strong>%{uploadProgress}</strong></div>
                <span className="progress-track"><i style={{ width: `${uploadProgress}%` }} /></span>
              </div>
            )}
          </div>
        )}

        <footer className="wizard-footer">
          <button className="button button--ghost" onClick={() => step === 1 ? navigate('/') : setStep(step - 1)} disabled={submitting}>
            <ArrowLeft size={17} /> {step === 1 ? 'Vazgeç' : 'Geri'}
          </button>
          {step < 3 ? (
            <button className="button button--primary" onClick={() => setStep(step + 1)} disabled={!canContinue}>
              Devam et <ArrowRight size={17} />
            </button>
          ) : (
            <button className="button button--primary" onClick={() => void submit()} disabled={submitting || !file}>
              {submitting ? <><LoaderCircle className="spin" size={17} /> Başlatılıyor…</> : <><Sparkles size={17} /> Analizi başlat</>}
            </button>
          )}
        </footer>
      </section>
    </div>
  )
}

function Toggle({ label, detail, checked, onChange }: { label: string; detail: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="toggle-row">
      <span><strong>{label}</strong><small>{detail}</small></span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <i aria-hidden="true" />
    </label>
  )
}
