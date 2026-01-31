import { useMemo } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  MessageSquare,
  FileText,
  Link2,
  Cpu,
  Bot,
  Users,
  Settings,
  Moon,
  Sun,
  ChevronLeft,
  ChevronRight,
  Plus,
  LogOut,
  Layers,
  LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/components/theme-provider'
import { useAuth, usePermissions } from '@/auth'
import { chatApi } from '@/api'
import {
  Button,
  ScrollArea,
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  Avatar,
  AvatarFallback,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui'

interface NavItem {
  icon: LucideIcon
  label: string
  href: string
  /** Permission required to see this item (optional) */
  permission?: string
  /** Role required to see this item (optional) */
  role?: string
}

const navItems: NavItem[] = [
  { icon: MessageSquare, label: 'Chat', href: '/' },
  { icon: FileText, label: 'Documents', href: '/documents' },
  { icon: Link2, label: 'Connectors', href: '/connectors', role: 'admin' },
  { icon: Layers, label: 'Embeddings', href: '/embedding-models', role: 'admin' },
  { icon: Cpu, label: 'LLMs', href: '/llms', role: 'admin' },
  { icon: Bot, label: 'Assistants', href: '/assistants' },
  { icon: Users, label: 'Users', href: '/users', role: 'admin' },
]

interface SidebarProps {
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
}

export function Sidebar({ collapsed, onCollapsedChange }: SidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { setTheme, resolvedTheme } = useTheme()
  const { user, logout } = useAuth()
  const { hasRole, can } = usePermissions()

  // Filter nav items based on user permissions
  const visibleNavItems = useMemo(() => {
    return navItems.filter((item) => {
      // Check role requirement
      if (item.role && !hasRole(item.role)) {
        return false
      }
      // Check permission requirement
      if (item.permission && !can(item.permission)) {
        return false
      }
      return true
    })
  }, [hasRole, can])

  const { data: sessionsData } = useQuery({
    queryKey: ['chat-sessions', { limit: 20 }],
    queryFn: () => chatApi.listSessions({ limit: 20 }),
  })

  const sessions = sessionsData?.sessions || []

  const handleNewChat = () => {
    navigate('/')
  }

  const handleLogout = async () => {
    await logout()
  }

  const userInitials = user
    ? `${user.profile.given_name?.[0] || ''}${user.profile.family_name?.[0] || ''}`.toUpperCase() ||
      user.profile.preferred_username?.[0]?.toUpperCase() ||
      'U'
    : 'U'

  return (
    <div
      className={cn(
        'flex h-full flex-col border-r bg-background transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b px-3">
        <div className="flex items-center gap-2">
          <img src="/logo.png" alt="EchoMind" className="h-8 w-8" />
          {!collapsed && <span className="font-semibold text-lg">EchoMind</span>}
        </div>
        <Button variant="ghost" size="icon" onClick={() => onCollapsedChange(!collapsed)}>
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {/* New Chat Button */}
      <div className="p-2">
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              className={cn('w-full', collapsed && 'px-0')}
              onClick={handleNewChat}
            >
              <Plus className="h-4 w-4" />
              {!collapsed && <span className="ml-2">New Chat</span>}
            </Button>
          </TooltipTrigger>
          {collapsed && <TooltipContent side="right">New Chat</TooltipContent>}
        </Tooltip>
      </div>

      {/* Chat Sessions (only when expanded) */}
      {!collapsed && sessions.length > 0 && (
        <div className="px-2">
          <p className="px-2 py-1 text-xs font-medium text-muted-foreground">Recent Chats</p>
          <ScrollArea className="h-[180px]">
            {sessions.map((session) => (
              <Link
                key={session.id}
                to={`/chat/${session.id}`}
                className={cn(
                  'block rounded-md px-2 py-1.5 text-sm truncate hover:bg-accent',
                  location.pathname === `/chat/${session.id}` && 'bg-accent'
                )}
              >
                {session.title || `Chat ${session.id}`}
              </Link>
            ))}
          </ScrollArea>
        </div>
      )}

      {/* Navigation */}
      <ScrollArea className="flex-1 px-2 py-2">
        <nav className="space-y-1">
          {visibleNavItems.map((item) => {
            const isActive =
              item.href === '/'
                ? location.pathname === '/' || location.pathname.startsWith('/chat')
                : location.pathname.startsWith(item.href)

            return (
              <Tooltip key={item.href} delayDuration={0}>
                <TooltipTrigger asChild>
                  <Link
                    to={item.href}
                    className={cn(
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground',
                      isActive
                        ? 'bg-accent text-accent-foreground'
                        : 'text-muted-foreground',
                      collapsed && 'justify-center px-0'
                    )}
                  >
                    <item.icon className="h-4 w-4 flex-shrink-0" />
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                </TooltipTrigger>
                {collapsed && <TooltipContent side="right">{item.label}</TooltipContent>}
              </Tooltip>
            )
          })}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t p-2 space-y-2">
        {/* Theme Toggle */}
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size={collapsed ? 'icon' : 'default'}
              className={cn('w-full', !collapsed && 'justify-start')}
              onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
            >
              {resolvedTheme === 'dark' ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
              {!collapsed && <span className="ml-2">Toggle Theme</span>}
            </Button>
          </TooltipTrigger>
          {collapsed && <TooltipContent side="right">Toggle Theme</TooltipContent>}
        </Tooltip>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className={cn('w-full', collapsed ? 'px-0' : 'justify-start gap-2')}
            >
              <Avatar className="h-6 w-6">
                <AvatarFallback className="text-xs">{userInitials}</AvatarFallback>
              </Avatar>
              {!collapsed && (
                <span className="truncate">
                  {user?.profile.given_name || user?.profile.preferred_username || 'User'}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align={collapsed ? 'center' : 'start'} side="top" className="w-48">
            <DropdownMenuLabel>
              {user?.profile.email || 'User'}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link to="/settings">
                <Settings className="mr-2 h-4 w-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="text-destructive">
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}
