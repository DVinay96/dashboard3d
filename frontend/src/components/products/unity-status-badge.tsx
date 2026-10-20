import { Badge } from '@/components/ui/badge'
import type { Tone } from '@/lib/format'

const STATES: Record<string, { label: string; tone: Tone }> = {
  PENDING: { label: 'Pendiente', tone: 'neutral' },
  SYNCING: { label: 'Sincronizando', tone: 'accent' },
  SYNCED: { label: 'Sincronizado', tone: 'ok' },
  FAILED: { label: 'Falló', tone: 'fail' },
}

export function UnityStatusBadge({ status }: { status: string }) {
  const s = STATES[status] ?? { label: status, tone: 'neutral' as const }
  return <Badge tone={s.tone}>{s.label}</Badge>
}
