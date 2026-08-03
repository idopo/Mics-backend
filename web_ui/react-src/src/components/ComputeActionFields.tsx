import type { FdaAction, ToolkitRead, HardwareModule } from '../types'

interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  hwModules: HardwareModule[]
  taskDefId?: number
  versionStamp?: string
  /** Declared FdaJson.variables names — the output combobox's option list. */
  variableNames?: string[]
  /** Declares a new name into FdaJson.variables the moment it's typed (CMP-13). */
  onDeclareVariable?: (name: string) => void
  onChange: (patch: Partial<FdaAction>) => void
}

// Stub — filled in by Task 2 (grouped op picker + mandatory output combobox).
export default function ComputeActionFields(_props: Props): JSX.Element {
  return <div />
}
