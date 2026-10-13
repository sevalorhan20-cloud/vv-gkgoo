import { ArrowRight, Check, Clapperboard, Inbox, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { getProjectStatusLabel, getScoreTone, isProjectActive, isProjectComplete, isProjectFailed } from '../utils'

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? 'brand--compact' : ''}`} aria-label="KlipForge Local">
      <span className="brand__mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      {!compact && (
        <span className="brand__name">
          KlipForge <em>Local</em>
        </span>
      )}
    </div>
  )
}

export function StatusPill({ status, progress }: { status?: string; progress?: number }) {
  const tone = isProjectComplete(status) ? 'success' : isProjectFailed(status) ? 'error' : isProjectActive(status) ? 'active' : 'neutral'
  return (
    <span className={`status-pill status-pill--${tone}`}>
      {tone === 'active' && <span className="status-pill__pulse" aria-hidden="true" />}
      {tone === 'success' && <Check size={13} aria-hidden="true" />}
      {getProjectStatusLabel(status)}
      {tone === 'active' && typeof progress === 'number' ? ` · %${Math.round(progress)}` : ''}
    </span>
  )
}

export function ScoreRing({ score, size = 'regular' }: { score: number; size?: 'small' | 'regular' | 'large' }) {
  const safeScore = Math.max(0, Math.min(Math.round(score), 100))
  return (
    <div
      className={`score-ring score-ring--${size} score-ring--${getScoreTone(safeScore)}`}
      style={{ '--score': `${safeScore * 3.6}deg` } as React.CSSProperties}
      role="img"
      aria-label={`Öne çıkma puanı 100 üzerinden ${safeScore}`}
    >
      <span>{safeScore}</span>
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon">{icon ?? <Inbox size={25} />}</div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  )
}

export function LoadingState({ label = 'Yükleniyor…' }: { label?: string }) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spin" size={24} />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="empty-state empty-state--error" role="alert">
      <div className="empty-state__icon"><Clapperboard size={25} /></div>
      <h3>Bir şey yolunda gitmedi</h3>
      <p>{message}</p>
      {onRetry && (
        <button className="button button--secondary" onClick={onRetry}>
          Yeniden dene <ArrowRight size={16} />
        </button>
      )}
    </div>
  )
}
