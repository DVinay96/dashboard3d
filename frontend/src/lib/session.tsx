import { createContext, useContext, useMemo, type ReactNode } from 'react'
import type { Me } from '@/api/types'

export interface Session {
  me: Me
  isSuper: boolean
  clientId: string | null
  can: (action: string) => boolean
  hasModule: (id: string) => boolean
}

const SessionContext = createContext<Session | null>(null)

export function SessionProvider({ me, children }: { me: Me; children: ReactNode }) {
  const value = useMemo<Session>(() => {
    const can = new Set(me.can)
    const modules = new Set(me.modules)
    return {
      me,
      isSuper: me.is_super_admin,
      clientId: me.client?.id ?? null,
      can: (a) => can.has(a),
      hasModule: (m) => modules.has(m),
    }
  }, [me])
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): Session {
  const s = useContext(SessionContext)
  if (!s) throw new Error('useSession fuera de SessionProvider')
  return s
}
