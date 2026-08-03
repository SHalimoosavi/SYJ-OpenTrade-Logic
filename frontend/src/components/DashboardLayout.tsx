import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  Search,
  Package,
  Users,
  LogOut,
  Terminal,
  Calculator,
  History,
  Webhook,
  Sun,
  Moon,
  Menu,
  X,
} from 'lucide-react'
import { useAuth } from '@/lib/auth-context'
import { useTheme } from '@/lib/theme-context'
import { cn } from '@/lib/utils'
import { roleAtLeast } from '@/types/api'

const navItems = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/classify', label: 'Classify', icon: Search },
  { to: '/duty-calculator', label: 'Duty Calculator', icon: Calculator },
  { to: '/products', label: 'Product Catalog', icon: Package },
  { to: '/members', label: 'Members', icon: Users, minRole: 'viewer' as const },
  { to: '/audit-log', label: 'Audit Log', icon: History, minRole: 'admin' as const },
  { to: '/webhooks', label: 'Webhooks', icon: Webhook, minRole: 'admin' as const },
]

export function DashboardLayout() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const sidebarContent = (
    <>
      <div className="flex items-center gap-2 border-b border-border px-5 py-5">
        <Terminal className="h-5 w-5 text-primary" />
        <div>
          <p className="text-sm font-semibold leading-none">SYJ OpenTrade</p>
          <p className="text-xs text-muted-foreground">Logic v0.9.0</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          if (item.minRole && user && !roleAtLeast(user.role, item.minRole)) return null
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMobileNavOpen(false)}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/15 text-primary'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                )
              }
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      <div className="border-t border-border p-4">
        <div className="mb-3 flex items-center gap-2 px-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
            {user?.full_name?.[0]?.toUpperCase() ?? '?'}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{user?.full_name}</p>
            <p className="truncate text-xs capitalize text-muted-foreground">{user?.role}</p>
          </div>
        </div>
        <button
          onClick={toggleTheme}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
        <button
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </>
  )

  return (
    <div className="flex h-screen bg-background">
      {/* Desktop sidebar -- always visible at md+ widths */}
      <aside className="hidden w-60 flex-col border-r border-border bg-card md:flex">{sidebarContent}</aside>

      {/* Mobile top bar -- only shown below md */}
      <div className="fixed inset-x-0 top-0 z-40 flex h-14 items-center justify-between border-b border-border bg-card px-4 md:hidden">
        <div className="flex items-center gap-2">
          <Terminal className="h-5 w-5 text-primary" />
          <span className="text-sm font-semibold">SYJ OpenTrade</span>
        </div>
        <button
          onClick={() => setMobileNavOpen(true)}
          className="rounded-md p-2 text-muted-foreground hover:bg-secondary hover:text-foreground"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      {/* Mobile slide-in nav + overlay */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setMobileNavOpen(false)} />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r border-border bg-card shadow-xl animate-in slide-in-from-left duration-200">
            <div className="flex items-center justify-end px-3 pt-3">
              <button
                onClick={() => setMobileNavOpen(false)}
                className="rounded-md p-2 text-muted-foreground hover:bg-secondary hover:text-foreground"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            {sidebarContent}
          </aside>
        </div>
      )}

      <main className="flex-1 overflow-y-auto pt-14 md:pt-0">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
