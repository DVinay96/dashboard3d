import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext } from '@tanstack/react-router'
import { useMe } from '@/api/queries'
import { AppShell } from '@/components/layout/app-shell'
import { Button } from '@/components/ui/button'
import { ConfirmProvider } from '@/components/ui/confirm'
import { Skeleton } from '@/components/ui/misc'
import { LightboxProvider } from '@/components/products/lightbox'
import { getIdentity, setIdentity } from '@/lib/identity'
import { SessionProvider } from '@/lib/session'

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({ component: Root })

function Root() {
  const me = useMe()

  if (me.isPending)
    return (
      <div className="mx-auto max-w-md space-y-3 p-10">
        <Skeleton className="h-8" />
        <Skeleton className="h-24" />
      </div>
    )

  if (me.isError) {
    const acting = !!getIdentity().actAs || !!getIdentity().clientId
    return (
      <div role="alert" className="mx-auto mt-24 max-w-md rounded-xl border border-line bg-panel p-6 text-center">
        <h1 className="mb-2 text-base font-semibold">No se pudo iniciar la sesión</h1>
        <p className="mb-5 text-[13px] text-muted">{me.error.message}</p>
        <div className="flex justify-center gap-2">
          <Button onClick={() => void me.refetch()}>Reintentar</Button>
          {acting && (
            <Button
              variant="outline"
              onClick={() => {
                setIdentity({ actAs: null, clientId: null })
                window.location.assign('/')
              }}
            >
              Volver a super admin
            </Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <SessionProvider me={me.data}>
      <ConfirmProvider>
        <LightboxProvider>
          <AppShell />
        </LightboxProvider>
      </ConfirmProvider>
    </SessionProvider>
  )
}
