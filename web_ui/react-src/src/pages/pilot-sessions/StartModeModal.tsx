import { useEffect } from 'react'

interface Props {
  runId: number
  status: string
  step: number | string | null | undefined
  trial: number | string | null | undefined
  canResume: boolean
  onChoice: (choice: 'resume' | 'restart' | 'new' | null) => void
}

export default function StartModeModal({ runId, status, step, trial, canResume, onChoice }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); onChoice(null) } }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [onChoice])

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onChoice(null) }}
    >
      <div className="modal">
        <div className="modal-header">
          <div className="modal-title">Previous run detected</div>
          <button className="modal-close" type="button" aria-label="Close" onClick={() => onChoice(null)}>✕</button>
        </div>

        <div className="modal-body">
          <div className="modal-muted">
            A run was stopped mid-way. Choose how to continue:
          </div>

          <div className="modal-kv">
            <div><span>Run ID</span><strong>{runId ?? '?'}</strong></div>
            <div><span>Status</span><strong>{status ?? '?'}</strong></div>
            <div><span>Progress</span><strong>step {step ?? '?'}, trial {trial ?? '?'}</strong></div>
          </div>

          <div className="modal-actions">
            <button className="button-primary" type="button" disabled={!canResume} onClick={() => onChoice('resume')}>
              Resume
              <span className="modal-sub">{canResume ? 'Continue from current step/trial' : 'No progress to resume from'}</span>
            </button>

            <button className="button-secondary" type="button" onClick={() => onChoice('restart')}>
              Restart
              <span className="modal-sub">Reset progress and start over</span>
            </button>

            <button className="button-secondary" type="button" onClick={() => onChoice('new')}>
              New run
              <span className="modal-sub">Create a fresh run record</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
