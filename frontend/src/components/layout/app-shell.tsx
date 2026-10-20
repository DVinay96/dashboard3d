import { Link, Outlet } from '@tanstack/react-router'
import { Boxes, Building2, FolderKanban, Gauge, KeyRound, ListChecks, Plug, Settings2, Tags, UploadCloud, Users } from 'lucide-react'
import { useEffect, type ComponentType } from 'react'
import { ClientSwitcher, ViewAs } from './context-switchers'
import { useSession } from '@/lib/session'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
  show: boolean
}

function NavLink({ item }: { item: NavItem }) {
  return (
    <Link
      to={item.to}
      className="flex items-center gap-2.5 rounded-lg px-3 py-2 font-medium whitespace-nowrap text-faint transition-colors hover:bg-panel-2 hover:text-fg"
      activeProps={{ className: 'bg-panel-2 text-fg shadow-[inset_0_0_0_1px_var(--color-line)]' }}
    >
      <item.icon className="size-4 shrink-0" />
      {item.label}
    </Link>
  )
}

export function AppShell() {
  const s = useSession()
  const client = s.me.client

  useEffect(() => {
    const root = document.documentElement
    const accent = client?.theme?.accent
    if (typeof accent === 'string') {
      root.style.setProperty('--color-accent', accent)
      root.style.setProperty('--color-accent-strong', `color-mix(in oklab, ${accent} 70%, black)`)
    }
    return () => {
      root.style.removeProperty('--color-accent')
      root.style.removeProperty('--color-accent-strong')
    }
  }, [client?.theme?.accent])

  const work: NavItem[] = [
    { to: '/products', label: 'Productos', icon: Boxes, show: s.can('products:list') },
    { to: '/projects', label: 'Proyectos', icon: FolderKanban, show: s.can('projects:read') },
    { to: '/brands', label: 'Marcas', icon: Tags, show: s.can('brands:read') },
    { to: '/unity', label: 'Unity', icon: UploadCloud, show: s.hasModule('unity') && s.can('unity:read') },
  ]
  const admin: NavItem[] = [
    { to: '/admin/setup', label: 'Puesta en marcha', icon: ListChecks, show: s.isSuper },
    { to: '/admin/clients', label: 'Clientes', icon: Building2, show: s.isSuper },
    { to: '/admin/users', label: 'Usuarios', icon: Users, show: s.isSuper },
    { to: '/admin/roles', label: 'Roles', icon: KeyRound, show: s.isSuper },
    { to: '/admin/access', label: 'Accesos', icon: Gauge, show: s.isSuper },
    { to: '/admin/integrations', label: 'Integraciones', icon: Plug, show: s.isSuper },
    { to: '/admin/platform', label: 'Plataforma', icon: Settings2, show: s.isSuper },
  ]
  const logo = typeof client?.theme?.logo_url === 'string' ? client.theme.logo_url : null

  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <aside className="shrink-0 border-b border-line bg-panel md:w-56 md:border-r md:border-b-0">
        <div className="flex items-center gap-2.5 px-4 py-3.5 md:py-4">
          {logo ? (
            <img src={logo} alt="" className="size-7 rounded-md object-contain" />
          ) : (
            <span className="grid size-7 place-items-center rounded-md bg-accent/15 text-accent">
              <Boxes className="size-4" />
            </span>
          )}
          <div className="min-w-0 leading-tight">
            <div className="truncate font-semibold">{client?.name ?? 'Pipeline 3D'}</div>
            <div className="text-[11px] text-faint">{client ? 'Pipeline 3D' : 'Plataforma'}</div>
          </div>
        </div>
        <nav aria-label="Principal" className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:overflow-visible md:pb-4">
          {work.filter((i) => i.show).map((i) => (
            <NavLink key={i.to} item={i} />
          ))}
          {s.isSuper && (
            <>
              <div className="hidden px-3 pt-4 pb-1 text-[10.5px] font-semibold tracking-wider text-faint uppercase md:block">
                Administración
              </div>
              {admin.map((i) => (
                <NavLink key={i.to} item={i} />
              ))}
            </>
          )}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className={cn('flex flex-wrap items-center gap-2 border-b border-line px-5 py-2.5')}>
          <div className="flex-1" />
          <ClientSwitcher />
          <ViewAs />
          <span className="hidden pl-2 text-xs text-faint sm:inline">
            {s.me.user.display_name || s.me.user.email}
          </span>
        </header>
        <main className="mx-auto w-full max-w-[1280px] flex-1 px-5 pt-5 pb-20">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
