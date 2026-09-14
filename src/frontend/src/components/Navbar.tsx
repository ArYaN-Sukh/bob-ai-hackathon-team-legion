import { Link, useLocation } from 'react-router-dom'
import { Activity, AlertTriangle, FileText, MessageSquare, LayoutDashboard, Users, Shield } from 'lucide-react'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/deviations', label: 'Deviations', icon: AlertTriangle },
  { to: '/patients', label: 'Patients', icon: Users },
  { to: '/capa', label: 'CAPA', icon: FileText },
  { to: '/bob', label: 'Ask Bob', icon: MessageSquare },
]

export default function Navbar() {
  const location = useLocation()

  return (
    <nav className="bg-clinical-navy border-b border-clinical-navy-light shadow-elevation">
      <div className="max-w-[1440px] mx-auto px-6 flex items-center justify-between h-16">
        <Link to="/" className="flex items-center gap-3">
          <div className="bg-white/10 p-2 rounded-lg">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-white text-lg leading-tight">TrialGuard</span>
            <span className="text-xs text-white/70 leading-tight">Clinical Trial Risk Monitor</span>
          </div>
        </Link>
        <div className="flex items-center gap-1">
          {nav.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                location.pathname === to
                  ? 'bg-white text-clinical-navy'
                  : 'text-white/80 hover:bg-white/10 hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  )
}
