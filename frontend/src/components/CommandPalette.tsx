import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Search,
  Calculator,
  Package,
  Users,
  History,
  Webhook,
  Sun,
  Moon,
  LogOut,
} from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { useAuth } from '@/lib/auth-context'
import { useTheme } from '@/lib/theme-context'
import { roleAtLeast } from '@/types/api'
import { cn } from '@/lib/utils'

interface CommandItem {
  id: string
  label: string
  group: 'Navigate' | 'Actions'
  icon: React.ComponentType<{ className?: string }>
  action: () => void
  minRole?: 'viewer' | 'admin'
  keywords?: string
}

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)

  const go = (path: string) => {
    navigate(path)
    onOpenChange(false)
  }

  const allItems: CommandItem[] = useMemo(
    () => [
      { id: 'nav-overview', label: 'Overview', group: 'Navigate', icon: LayoutDashboard, action: () => go('/') },
      { id: 'nav-classify', label: 'Classify a product', group: 'Navigate', icon: Search, action: () => go('/classify') },
      {
        id: 'nav-duty',
        label: 'Duty Calculator',
        group: 'Navigate',
        icon: Calculator,
        action: () => go('/duty-calculator'),
      },
      { id: 'nav-products', label: 'Product Catalog', group: 'Navigate', icon: Package, action: () => go('/products') },
      {
        id: 'nav-members',
        label: 'Members',
        group: 'Navigate',
        icon: Users,
        action: () => go('/members'),
        minRole: 'viewer',
      },
      {
        id: 'nav-audit',
        label: 'Audit Log',
        group: 'Navigate',
        icon: History,
        action: () => go('/audit-log'),
        minRole: 'admin',
      },
      {
        id: 'nav-webhooks',
        label: 'Webhooks',
        group: 'Navigate',
        icon: Webhook,
        action: () => go('/webhooks'),
        minRole: 'admin',
      },
      {
        id: 'action-theme',
        label: theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode',
        group: 'Actions',
        icon: theme === 'dark' ? Sun : Moon,
        action: () => {
          toggleTheme()
          onOpenChange(false)
        },
        keywords: 'theme dark light appearance',
      },
      {
        id: 'action-signout',
        label: 'Sign out',
        group: 'Actions',
        icon: LogOut,
        action: () => {
          logout()
          onOpenChange(false)
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme]
  )

  const visibleItems = allItems.filter((item) => !item.minRole || (user && roleAtLeast(user.role, item.minRole)))

  const filteredItems = useMemo(() => {
    if (!query.trim()) return visibleItems
    const q = query.toLowerCase()
    return visibleItems.filter(
      (item) => item.label.toLowerCase().includes(q) || item.keywords?.toLowerCase().includes(q)
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, visibleItems.length, user?.role])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
    }
  }, [open])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => Math.min(i + 1, filteredItems.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      filteredItems[selectedIndex]?.action()
    }
  }

  const groups: CommandItem['group'][] = ['Navigate', 'Actions']

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[20%] max-w-lg translate-y-0 gap-0 p-0" onKeyDown={handleKeyDown}>
        <div className="flex items-center border-b border-border px-4">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search actions and pages..."
            className="flex-1 bg-transparent px-3 py-3 text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="hidden shrink-0 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground sm:inline">
            ESC
          </kbd>
        </div>

        <div className="max-h-80 overflow-y-auto p-2">
          {filteredItems.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">No matching actions.</p>
          )}
          {groups.map((group) => {
            const groupItems = filteredItems.filter((i) => i.group === group)
            if (groupItems.length === 0) return null
            return (
              <div key={group} className="mb-2 last:mb-0">
                <p className="px-3 py-1 text-xs font-medium text-muted-foreground">{group}</p>
                {groupItems.map((item) => {
                  const globalIndex = filteredItems.indexOf(item)
                  const Icon = item.icon
                  return (
                    <button
                      key={item.id}
                      onClick={item.action}
                      onMouseEnter={() => setSelectedIndex(globalIndex)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors',
                        globalIndex === selectedIndex ? 'bg-primary/15 text-primary' : 'text-foreground hover:bg-secondary'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </button>
                  )
                })}
              </div>
            )
          })}
        </div>
      </DialogContent>
    </Dialog>
  )
}
