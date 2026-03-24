import { Outlet, useLocation, Link } from 'react-router-dom'
import { Suspense, useEffect } from 'react'
import PageSkeleton from './PageSkeleton'

const NAV_LINKS = [
  {
    to: '/',
    label: 'Pilots',
    exact: true,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="2" />
        <path d="M16.24 7.76a6 6 0 0 1 0 8.49" />
        <path d="M7.76 7.76a6 6 0 0 0 0 8.49" />
        <path d="M20.07 4.93a10 10 0 0 1 0 14.14" />
        <path d="M3.93 4.93a10 10 0 0 0 0 14.14" />
      </svg>
    ),
  },
  {
    to: '/subjects-ui',
    label: 'Subjects',
    exact: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
      </svg>
    ),
  },
  {
    to: '/protocols-ui',
    label: 'Protocols',
    exact: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2.5" />
        <path d="M7 8h10M7 12h10M7 16h6" />
      </svg>
    ),
  },
  {
    to: '/projects-ui',
    label: 'Projects',
    exact: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 7a2 2 0 0 1 2-2h4l2 2h10a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z" />
      </svg>
    ),
  },
  {
    to: '/researchers-ui',
    label: 'Researchers',
    exact: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="9" cy="7" r="4" />
        <path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        <path d="M21 21v-2a4 4 0 0 0-3-3.85" />
      </svg>
    ),
  },
  {
    to: '/iacuc-ui',
    label: 'IACUC',
    exact: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
  },
  {
    to: '/task-definitions-ui',
    label: 'Tasks',
    exact: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 3v2M12 19v2M3 12h2M19 12h2" />
        <path d="M6.34 6.34l1.42 1.42M16.24 16.24l1.42 1.42M6.34 17.66l1.42-1.42M16.24 7.76l1.42-1.42" />
      </svg>
    ),
  },
  {
    to: '/toolkits-ui',
    label: 'Toolkits',
    exact: false,
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="7" width="20" height="15" rx="2" />
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
        <line x1="12" y1="12" x2="12" y2="17" />
        <line x1="9.5" y1="14.5" x2="14.5" y2="14.5" />
      </svg>
    ),
  },
]

function BrandMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <rect x="0"  y="0"  width="10" height="10" rx="2.5" fill="#818cf8" />
      <rect x="12" y="0"  width="10" height="10" rx="2.5" fill="#818cf8" opacity="0.5" />
      <rect x="0"  y="12" width="10" height="10" rx="2.5" fill="#818cf8" opacity="0.5" />
      <rect x="12" y="12" width="10" height="10" rx="2.5" fill="#818cf8" opacity="0.2" />
    </svg>
  )
}

export default function Layout() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  const isActive = (to: string, exact: boolean) => {
    if (exact) return pathname === to || pathname.startsWith('/pilots')
    const base = to.replace('-ui', '')
    return pathname === to || pathname.startsWith(base + '/')
  }

  return (
    <div className="app-shell" style={{ height: '100vh', minHeight: 0, overflow: 'hidden' }}>
      <aside className="sidebar">
        <Link to="/" className="sidebar-brand" aria-label="MICS home">
          <BrandMark />
          <div className="brand-text">
            <span className="brand-name">MICS</span>
            <span className="brand-sub">Modular Interactive<br />Control System</span>
          </div>
        </Link>

        <nav className="sidebar-nav">
          {NAV_LINKS.map(({ to, label, icon, exact }) => (
            <Link
              key={to}
              to={to}
              className={isActive(to, exact) ? 'active' : undefined}
            >
              {icon}
              {label}
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="sidebar-version">MICS v0.1</span>
        </div>
      </aside>

      <main className="main-content" style={{ height: '100vh', minHeight: 0, overflowY: 'auto', boxSizing: 'border-box', padding: '2rem 3rem' }}>
        <Suspense fallback={<PageSkeleton />}>
          <Outlet />
        </Suspense>
      </main>

      {/* Fixed powered-by strip — same height as .sidebar-footer (14px pad × 2 + ~17px line) */}
      <div style={{
        position: 'fixed', bottom: 0, left: 'var(--sidebar-w, 260px)', right: 0,
        height: '46px',
        padding: '0 24px',
        display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px',
        background: 'var(--bg)',
        zIndex: 50,
        pointerEvents: 'none',
      }}>
        <span style={{ fontSize: '10px', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--subtext0)', opacity: 0.65 }}>powered by</span>
        <img src="/static/yizhar-lab.jpg" alt="Yizhar Lab" style={{ height: '26px', width: 'auto', mixBlendMode: 'screen', opacity: 0.95 }} />
        <span style={{ fontSize: '12px', letterSpacing: '0.05em', color: 'var(--subtext0)', opacity: 0.75, fontWeight: 600 }}>Yizhar Lab</span>
      </div>
    </div>
  )
}
