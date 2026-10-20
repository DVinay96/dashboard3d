import { CloudUpload } from 'lucide-react'
import { useUnitySync } from '@/api/queries'
import { UNITY_ACTIVE, type Product } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useSession } from '@/lib/session'
import { UnityStatusBadge } from './unity-status-badge'

export function UnitySection({ product: p }: { product: Product }) {
  const s = useSession()
  const sync = useUnitySync()
  if (!s.hasModule('unity') || !s.can('unity:read')) return null

  const withTarget = p.projects.length
  const busy = p.unity.some((r) => UNITY_ACTIVE.includes(r.status))
  const allSynced = p.unity.length > 0 && p.unity.every((r) => r.status === 'SYNCED')
  const canSync = s.can('unity:sync') && p.status === 'DONE' && withTarget > 0 && !busy && !allSynced

  return (
    <div className="rounded-lg border border-line bg-bg p-3.5">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-xs font-semibold tracking-wider text-muted uppercase">Unity Asset Manager</h3>
        <div className="flex-1" />
        {canSync && (
          <Button size="sm" loading={sync.isPending} onClick={() => sync.mutate(p.id)}>
            <CloudUpload className="size-3.5" /> {p.unity.some((r) => r.status === 'FAILED') ? 'Reintentar' : 'Sincronizar con Unity'}
          </Button>
        )}
      </div>
      {p.unity.length === 0 ? (
        <p className="text-xs text-faint">
          {p.status === 'DONE' ? 'Todavía no se publicó en Unity.' : 'Se puede publicar cuando el producto termine sin fallos de QA.'}
        </p>
      ) : (
        <ul className="space-y-1.5">
          {p.unity.map((r) => (
            <li key={r.id} className="text-[12.5px]">
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{r.project_name}</Badge>
                <UnityStatusBadge status={r.status} />
                {r.unity_asset_id && <span className="font-mono text-[11px] text-faint">asset {r.unity_asset_id}</span>}
              </div>
              {r.error && <p className="mt-1 text-xs break-words text-fail">{r.error}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
