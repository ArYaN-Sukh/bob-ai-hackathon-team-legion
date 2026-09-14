import type { DeviationSeverity, DeviationStatus } from '../types'

const SEVERITY_STYLES: Record<DeviationSeverity, string> = {
  Major: 'bg-severity-major-light text-severity-major border border-severity-major',
  Minor: 'bg-severity-minor-light text-severity-minor border border-severity-minor',
  Administrative: 'bg-severity-admin-light text-severity-admin border border-severity-admin',
}

const STATUS_STYLES: Record<string, string> = {
  Open: 'bg-severity-major-light text-severity-major',
  Closed: 'bg-risk-low-light text-risk-low',
  'Pending Review': 'bg-severity-minor-light text-severity-minor',
}

interface Props {
  value: DeviationSeverity | DeviationStatus | string
  type: 'severity' | 'status'
  size?: 'sm' | 'md'
}

export default function DeviationBadge({ value, type, size = 'md' }: Props) {
  const styles = type === 'severity'
    ? SEVERITY_STYLES[value as DeviationSeverity] ?? 'bg-surface-alt text-text-secondary'
    : STATUS_STYLES[value] ?? 'bg-surface-alt text-text-secondary'

  const sizeClass = size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-xs px-2 py-1'

  return (
    <span className={`inline-flex items-center font-medium rounded ${sizeClass} ${styles}`}>
      {value}
    </span>
  )
}
