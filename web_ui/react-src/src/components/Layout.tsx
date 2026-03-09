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
    <div className="app-shell">
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

      <main className="main-content">
        <Suspense fallback={<PageSkeleton />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}
