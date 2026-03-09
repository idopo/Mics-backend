import { Link, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'Pilots' },
  { to: '/subjects-ui', label: 'Subjects' },
  { to: '/protocols-ui', label: 'Protocols' },
  { to: '/protocols-create', label: 'New Protocol' },
]

export default function Nav() {
  const { pathname } = useLocation()
  return (
    <nav className="nav">
      {links.map(({ to, label }) => (
        <Link
          key={to}
          to={to}
          className={pathname === to ? 'nav-link active' : 'nav-link'}
        >
          {label}
        </Link>
      ))}
    </nav>
  )
}
