import React from 'react'
import type { ConditionGroup, FdaCondition, ToolkitRead } from '../types'
import { ConditionRow } from './ConditionBuilder'

const EMPTY_CONDITION: FdaCondition = { left: { view: '' }, op: '==', right: 0 }

interface Props {
  groups: ConditionGroup[]
  toolkit: ToolkitRead | null
  hwModuleNames?: string[]
  onChange: (groups: ConditionGroup[]) => void
}

export function ConditionGroupsEditor({ groups, toolkit, hwModuleNames, onChange }: Props) {

  const updateCondition = (gi: number, ci: number, updated: FdaCondition) =>
    onChange(groups.map((g, i) =>
      i !== gi ? g : { conditions: g.conditions.map((c, j) => j === ci ? updated : c) }
    ))

  const deleteCondition = (gi: number, ci: number) => {
    const newConds = groups[gi].conditions.filter((_, j) => j !== ci)
    if (newConds.length === 0) {
      onChange(groups.filter((_, i) => i !== gi))       // remove empty group
    } else {
      onChange(groups.map((g, i) => i !== gi ? g : { conditions: newConds }))
    }
  }

  const addAndCondition = (gi: number) =>
    onChange(groups.map((g, i) =>
      i !== gi ? g : { conditions: [...g.conditions, { ...EMPTY_CONDITION }] }
    ))

  const addOrGroup = () =>
    onChange([...groups, { conditions: [{ ...EMPTY_CONDITION }] }])

  return (
    <div>
      {groups.length === 0 && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '2px 0 6px',
                      fontStyle: 'italic' }}>
          unconditional — fires immediately
        </div>
      )}

      {groups.map((group, gi) => (
        <React.Fragment key={gi}>
          {gi > 0 && (
            <div style={{ textAlign: 'center', padding: '3px 0', fontSize: 10,
                          color: 'var(--accent)', fontWeight: 700, letterSpacing: 1 }}>
              OR
            </div>
          )}

          <div style={{ border: '1px solid var(--border)', borderRadius: 4,
                        padding: '6px 8px', marginBottom: 2 }}>
            {group.conditions.map((cond, ci) => (
              <React.Fragment key={ci}>
                {ci > 0 && (
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700,
                                padding: '2px 0', letterSpacing: 1 }}>
                    AND
                  </div>
                )}
                <ConditionRow
                  condition={cond}
                  toolkit={toolkit}
                  hwModuleNames={hwModuleNames}
                  onChange={updated => updateCondition(gi, ci, updated)}
                  onDelete={() => deleteCondition(gi, ci)}
                />
              </React.Fragment>
            ))}

            <button
              onClick={() => addAndCondition(gi)}
              style={{ marginTop: 4, fontSize: 11, background: 'none', border: 'none',
                       color: 'var(--accent)', cursor: 'pointer', padding: '2px 4px' }}
            >+ AND</button>
          </div>
        </React.Fragment>
      ))}

      <button
        onClick={addOrGroup}
        style={{ marginTop: 6, fontSize: 11, background: 'none',
                 border: '1px dashed var(--border)', color: 'var(--accent)',
                 cursor: 'pointer', borderRadius: 4, padding: '4px 10px', width: '100%' }}
      >+ OR group</button>
    </div>
  )
}
