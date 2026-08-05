import { BaseEdge, type EdgeProps } from '@xyflow/react'
import {
  quadraticControlPoint,
  quadraticPath,
  pointOnQuadratic,
  selfLoopPath,
  backEdgePath,
  type EdgeGeometry,
} from '../../components/edgeGeometry.mts'

const DEFAULT_GEOMETRY: EdgeGeometry = {
  index: 0,
  kind: 'pair',
  groupSize: 1,
  memberIndex: 0,
  offset: 0,
  reversed: false,
  labelT: 0.5,
  backSpan: 0,
}

/** Custom react-flow edge: bows parallel pairs apart, loops self-transitions, routes back-edges. */
export default function TransitionEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  markerEnd,
  label,
  labelStyle,
  labelBgStyle,
  style,
  selected,
}: EdgeProps): JSX.Element | null {
  if (
    !Number.isFinite(sourceX) ||
    !Number.isFinite(sourceY) ||
    !Number.isFinite(targetX) ||
    !Number.isFinite(targetY)
  ) {
    return null
  }

  const geometry = (data?.geometry as EdgeGeometry | undefined) ?? DEFAULT_GEOMETRY
  const a = { x: sourceX, y: sourceY }
  const b = { x: targetX, y: targetY }

  let path: string
  let labelPoint: { x: number; y: number }
  if (geometry.kind === 'self') {
    ;({ path, labelPoint } = selfLoopPath(a, b, geometry.offset))
  } else if (geometry.kind === 'back') {
    ;({ path, labelPoint } = backEdgePath(a, b, geometry.offset))
  } else {
    const c = quadraticControlPoint(a, b, geometry.offset)
    path = quadraticPath(a, c, b)
    labelPoint = pointOnQuadratic(a, c, b, geometry.labelT)
  }

  return (
    <BaseEdge
      id={id}
      path={path}
      markerEnd={markerEnd}
      labelX={labelPoint.x}
      labelY={labelPoint.y}
      label={label}
      labelStyle={labelStyle}
      labelBgStyle={labelBgStyle}
      labelBgPadding={[3, 5]}
      labelBgBorderRadius={3}
      style={{ ...style, strokeWidth: selected ? 2.5 : 1.5 }}
      interactionWidth={20}
    />
  )
}
