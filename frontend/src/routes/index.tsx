import { Navigate, createFileRoute } from '@tanstack/react-router'
import { useSession } from '@/lib/session'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  const s = useSession()
  return s.isSuper && !s.me.client ? <Navigate to="/admin/setup" replace /> : <Navigate to="/products" replace />
}
