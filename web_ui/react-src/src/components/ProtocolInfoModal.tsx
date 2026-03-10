import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import ProtocolInfoContent from './ProtocolInfoContent'

interface Props {
  protocolId: number
  onClose: () => void
}

export default function ProtocolInfoModal({ protocolId, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [onClose])

  return createPortal(
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="modal"
        style={{
          width: 'min(860px, calc(100vw - 24px))',
          maxWidth: '860px',
          minHeight: '480px',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '90vh',
        }}
      >
        <div className="modal-header">
          <div className="modal-title">Protocol Info</div>
          <button className="modal-close" type="button" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body" style={{ overflowY: 'auto', flex: '1 1 0', minHeight: 0, padding: '16px' }}>
          <ProtocolInfoContent protocolId={protocolId} showFullParams />
        </div>
      </div>
    </div>,
    document.body
  )
}
