interface Props {
  status: string
}

const statusClass: Record<string, string> = {
  connected: 'badge-connected',
  disconnected: 'badge-disconnected',
  running: 'badge-running',
  stopped: 'badge-stopped',
}

export default function StatusBadge({ status }: Props) {
  const cls = statusClass[(status ?? '').toLowerCase()] ?? 'badge-disconnected'
  return <span className={`status-badge ${cls}`}>{status ?? '—'}</span>
}
