import { Box, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { ACTIVE_STATUSES, type Product, type QaMetrics } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { ProductDetail } from './product-detail'
import { StatusBadge } from './status-badge'

function thumbnail(p: Product): string | null {
  if (p.photos.length) return `/api/products/${p.id}/files/input/${p.photos[0]}`
  const m = p.metrics as QaMetrics | null
  if (m) return `/api/products/${p.id}/files/qa/${(m.renders ?? []).includes('tex_q34.png') ? 'tex_q34' : 'q34'}.png`
  return null
}

function subtitle(p: Product): string {
  const m = p.metrics as (QaMetrics & { summary?: { pass: number; warn: number; fail: number } }) | null
  const parts: (string | null)[] = [
    p.brand_name || null,
    p.source === 'local' ? 'modelo local' : p.source === 'retexture' ? 'material nuevo' : `${p.photos.length} foto${p.photos.length === 1 ? '' : 's'}`,
    p.credits ? `${p.credits} créditos` : null,
    m?.summary ? `${m.summary.pass} ok · ${m.summary.warn} avisos · ${m.summary.fail} fallos` : p.stage,
  ]
  return parts.filter(Boolean).join(' · ')
}

export function ProductCard({ product: p }: { product: Product }) {
  const [open, setOpen] = useState(false)
  const active = ACTIVE_STATUSES.includes(p.status)
  const thumb = thumbnail(p)
  return (
    <article className="mb-3.5 rounded-[10px] border border-line bg-panel p-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center gap-3 text-left"
      >
        <span className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-lg border border-line bg-bg text-faint">
          {thumb ? <img src={thumb} alt="" loading="lazy" className="size-full object-cover" /> : <Box className="size-5" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14.5px] font-semibold">{p.name}</span>
          <span className="block truncate text-xs text-faint">{subtitle(p)}</span>
          {p.projects.length > 0 && (
            <span className="mt-1 flex flex-wrap gap-1">
              {p.projects.slice(0, 3).map((x) => (
                <Badge key={x.id}>{x.name}</Badge>
              ))}
              {p.projects.length > 3 && <Badge>+{p.projects.length - 3}</Badge>}
            </span>
          )}
        </span>
        <StatusBadge status={p.status} />
        <ChevronRight className={cn('size-4 shrink-0 text-faint transition-transform', open && 'rotate-90')} />
      </button>
      {active && (
        <div
          role="progressbar"
          aria-valuenow={p.progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Progreso"
          className="mt-2.5 h-1 overflow-hidden rounded-full bg-line"
        >
          <div
            className={cn('h-full rounded-full bg-accent transition-[width]', !p.progress && 'w-1/3 animate-pulse')}
            style={p.progress ? { width: `${p.progress}%` } : undefined}
          />
        </div>
      )}
      {open && (
        <div className="mt-3">
          <ProductDetail product={p} />
        </div>
      )}
    </article>
  )
}
