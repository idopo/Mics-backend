import { useQuery } from '@tanstack/react-query'
import { getVariableUsage } from '../api/task-definitions'
import type { VariableUsage } from '../types'

interface Props {
  taskDefId?: number
}

const locationList: React.CSSProperties = {
  margin: '2px 0 0',
  paddingLeft: '16px',
  fontSize: '11px',
  fontFamily: "'IBM Plex Mono', monospace",
  color: 'var(--muted)',
}

/** One variable's writer/reader locations — collapsed by default, nothing to click but the toggle. */
function VariableUsageRow({ name, usage }: { name: string; usage: VariableUsage }): JSX.Element {
  return (
    <div style={{ padding: '4px 0', borderBottom: '1px solid var(--overlay0)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '12px' }}>{name}</span>
        {usage.never_written && (
          <span className="badge status-error" style={{ fontSize: '10px' }}>never written</span>
        )}
      </div>
      <details>
        <summary style={{ fontSize: '11px', color: 'var(--muted)', cursor: 'pointer' }}>
          {usage.writers.length} writer{usage.writers.length === 1 ? '' : 's'},{' '}
          {usage.readers.length} reader{usage.readers.length === 1 ? '' : 's'}
        </summary>
        {usage.writers.length > 0 && (
          <ul style={locationList}>
            {usage.writers.map(loc => <li key={`w:${loc}`}>write · {loc}</li>)}
          </ul>
        )}
        {usage.readers.length > 0 && (
          <ul style={locationList}>
            {usage.readers.map(loc => <li key={`r:${loc}`}>read · {loc}</li>)}
          </ul>
        )}
      </details>
    </div>
  )
}

/**
 * Read-only variable -> writers/readers inspector (CMP-15). Not an authoring surface —
 * declaration stays inline in the compute action's output field. The backend owns the FDA
 * walk (api/variable_scan.py); this only renders what it returns.
 */
export default function VariableUsagePanel({ taskDefId }: Props): JSX.Element {
  const { data } = useQuery({
    queryKey: ['variable-usage', taskDefId],
    queryFn: () => getVariableUsage(taskDefId!),
    enabled: !!taskDefId,
    // The panel typically stays mounted (collapsed) across a save — refetch on every mount
    // is the only way to notice a saved FDA changed writer/reader locations.
    refetchOnMount: 'always',
  })

  const entries = Object.entries(data?.variables ?? {})

  if (entries.length === 0) {
    return <p style={{ fontSize: '11px', color: 'var(--muted)', margin: '4px 0 0' }}>No variables to inspect.</p>
  }

  return (
    <div style={{ marginTop: '4px' }}>
      {entries.map(([name, usage]) => (
        <VariableUsageRow key={name} name={name} usage={usage} />
      ))}
    </div>
  )
}
