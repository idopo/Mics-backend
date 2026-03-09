import type { CSSProperties } from 'react'

export default function Skeleton({ style }: { style?: CSSProperties }) {
  return <div className="skeleton" style={style} />
}
