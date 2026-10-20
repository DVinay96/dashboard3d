import { Building2, Eye, ChevronDown, Shield } from 'lucide-react'
import { useClients, useDevIdentities } from '@/api/queries'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { getIdentity, setIdentity } from '@/lib/identity'
import { useSession } from '@/lib/session'

function applyIdentity(patch: Parameters<typeof setIdentity>[0]) {
  setIdentity(patch)
  window.location.assign('/products')
}

export function ClientSwitcher() {
  const s = useSession()
  const clients = useClients()
  if (!s.isSuper) return null
  const current = s.me.client
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" aria-label="Cliente activo">
          <Building2 className="size-3.5" />
          {current ? current.name : 'Sin cliente'}
          <ChevronDown className="size-3.5 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>Operar sobre el cliente</DropdownMenuLabel>
        {(clients.data ?? []).map((c) => (
          <DropdownMenuItem key={c.id} onSelect={() => applyIdentity({ clientId: c.id })}>
            {c.name}
            {c.disabled && <span className="ml-auto text-xs text-faint">deshabilitado</span>}
          </DropdownMenuItem>
        ))}
        {clients.data?.length === 0 && <div className="px-2.5 py-1.5 text-xs text-faint">Todavía no hay clientes.</div>}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => applyIdentity({ clientId: null })}>Solo administración</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function ViewAs() {
  const s = useSession()
  const ids = useDevIdentities()
  if (s.me.auth_mode !== 'none' || !ids.data) return null
  const acting = getIdentity().actAs
  const users = ids.data.users
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant={acting ? 'default' : 'outline'} size="sm" aria-label="Ver como otro usuario">
          <Eye className="size-3.5" />
          {acting ? s.me.user.email : 'Ver como…'}
          <ChevronDown className="size-3.5 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="max-h-96 overflow-y-auto">
        <DropdownMenuItem onSelect={() => applyIdentity({ actAs: null })}>
          <Shield className="size-3.5" /> Super admin
        </DropdownMenuItem>
        {users.length > 0 && <DropdownMenuSeparator />}
        {users.map((u) => (
          <DropdownMenuItem key={u.id} onSelect={() => applyIdentity({ actAs: u.id, clientId: null })}>
            <span className="min-w-0 flex-1 truncate">
              {u.email}
              <small className="block text-xs text-faint">{u.client_name ?? 'Plataforma'}</small>
            </span>
            {u.id === acting && <span className="text-xs text-accent">actual</span>}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
