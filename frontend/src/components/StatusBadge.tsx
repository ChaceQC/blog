type StatusTone = 'draft' | 'published' | 'pending' | 'healthy'

type StatusBadgeProps = {
  tone: StatusTone
  children: string
}

export function StatusBadge({ tone, children }: StatusBadgeProps) {
  return <span className={`status-badge status-badge--${tone}`}>{children}</span>
}
