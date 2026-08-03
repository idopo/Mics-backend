import type { PreflightIssue } from './HardwareCheckModal'

/**
 * Read-only detail for the three compute-related preflight issues (CMP-15/17/19). Like
 * `ViewKeyIssueDetail`, there is nothing to edit here: the fix is a task-definition change, a
 * version promotion on the Hardware Libraries page, or a lib source fix — never a config PUT.
 */
export default function ComputeIssueDetail({ issue }: { issue: PreflightIssue }): JSX.Element {
  if (issue.issue === 'variable_never_written') {
    return (
      <div>
        <p style={{ margin: '0 0 8px', fontSize: '14px', fontFamily: 'monospace' }}>{issue.variable}</p>
        {issue.location && (
          <p style={{ margin: '0 0 8px', fontSize: '12px', color: 'var(--subtext0)' }}>
            read at <span style={{ fontFamily: 'monospace' }}>{issue.location}</span>
          </p>
        )}
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--subtext0)' }}>
          {issue.detail || 'Nothing writes this variable, so the guard compares it against None.'}
        </p>
      </div>
    )
  }

  if (issue.issue === 'lib_version_unresolved') {
    return (
      <div>
        <p style={{ margin: '0 0 8px', fontSize: '14px', fontFamily: 'monospace' }}>
          {issue.module_name} — {issue.lib_filename}
        </p>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--subtext0)' }}>
          {issue.detail || 'No beta/stable version is available to deploy. Promoting a version on the Hardware Libraries page fixes this.'}
        </p>
      </div>
    )
  }

  if (issue.issue === 'compute_lib_import_failed') {
    return (
      <div>
        <p style={{ margin: '0 0 8px', fontSize: '14px', fontFamily: 'monospace' }}>
          {issue.module_name} — {issue.lib_filename}
        </p>
        {issue.error && (
          <p style={{ margin: '0 0 8px', fontSize: '12px', fontFamily: 'monospace', color: 'var(--red)' }}>
            {issue.error}
          </p>
        )}
        {!issue.error && issue.detail && (
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--subtext0)' }}>{issue.detail}</p>
        )}
      </div>
    )
  }

  return <p style={{ margin: 0, fontSize: '13px', color: 'var(--subtext0)' }}>{issue.detail}</p>
}
