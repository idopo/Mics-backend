/** Reusable items-driven right-click menu for the FDA canvas. Styling lifted verbatim from the
 *  node context menu TaskEditor.tsx used to render inline. */
export interface ContextMenuItem {
  label: string
  danger?: boolean
  onClick: () => void
}

export default function CanvasContextMenu(props: {
  x: number
  y: number
  items: ContextMenuItem[]
  onClose: () => void
}): JSX.Element {
  const { x, y, items, onClose } = props
  return (
    <div
      style={{
        position: 'fixed', top: y, left: x,
        background: 'var(--panel)', border: '1px solid var(--border)',
        borderRadius: 6, padding: '4px 0', zIndex: 1000,
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
      }}
      onMouseLeave={onClose}
    >
      {items.map((item, i) => (
        <button
          key={i}
          style={{
            display: 'block', width: '100%', padding: '6px 14px',
            background: 'none', border: 'none', color: item.danger ? '#f87171' : 'var(--text)',
            cursor: 'pointer', textAlign: 'left', fontSize: 13,
          }}
          onClick={() => { item.onClick(); onClose() }}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
