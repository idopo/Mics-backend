import { Outlet, useLocation, Link } from 'react-router-dom'
import { Suspense, useEffect } from 'react'
import PageSkeleton from './PageSkeleton'

const NAV_LINKS = [
  { to: '/', label: 'Pilots' },
  { to: '/subjects-ui', label: 'Subjects' },
  { to: '/protocols-ui', label: 'Protocols' },
]

export default function Layout() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  return (
    <>
      <header>
        <pre className="ascii-logo">{`    ███╗   ███╗ ██╗ ██████╗ ███████╗
    ████╗ ████║ ██║██╔════╝ ██╔════╝
    ██╔████╔██║ ██║██║      ███████╗
    ██║╚██╔╝██║ ██║██║      ╚════██║
    ██║ ╚═╝ ██║ ██║╚██████╗ ███████║
    ╚═╝     ╚═╝ ╚═╝ ╚═════╝ ╚══════╝`}</pre>
        <nav>
          {NAV_LINKS.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              className={pathname === to ? 'active' : undefined}
            >
              {label}
            </Link>
          ))}
        </nav>
      </header>
      <main>
        <Suspense fallback={<PageSkeleton />}>
          <Outlet />
        </Suspense>
      </main>
    </>
  )
}
