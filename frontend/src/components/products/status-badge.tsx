import { Badge } from '@/components/ui/badge'
import { STATUS } from '@/lib/format'

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: 'neutral' as const }
  return <Badge tone={s.tone}>{s.label}</Badge>
}
