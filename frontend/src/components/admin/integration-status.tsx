import { CheckCircle2, CircleAlert, CircleDashed } from 'lucide-react'
import type { Integration } from '@/api/types'
import { fmtDate } from '@/lib/format'

export function IntegrationStatus({ integration: i, configured }: { integration: Integration; configured: boolean }) {
  if (i.last_status === 'OK')
    return (
      <p className="flex items-start gap-2 text-[12.5px] text-ok">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
        <span>
          {i.last_message} <span className="text-faint">· {fmtDate(i.last_at)}</span>
        </span>
      </p>
    )
  if (i.last_status === 'FAILED')
    return (
      <p role="alert" className="flex items-start gap-2 text-[12.5px] break-words text-fail">
        <CircleAlert className="mt-0.5 size-4 shrink-0" />
        <span>
          {i.last_message} <span className="text-faint">· {fmtDate(i.last_at)}</span>
        </span>
      </p>
    )
  return (
    <p className="flex items-center gap-2 text-[12.5px] text-faint">
      <CircleDashed className="size-4 shrink-0" />
      {configured ? 'Credenciales cargadas, sin probar todavía.' : 'Sin conectar.'}
    </p>
  )
}
