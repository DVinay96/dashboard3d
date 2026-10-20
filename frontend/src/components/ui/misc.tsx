import { Loader2 } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Skeleton({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('animate-pulse rounded-lg bg-panel-2', className)} {...props} />
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('size-4 animate-spin text-muted', className)} aria-label="Cargando" />
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center text-faint">
      {icon && <div className="mb-3 text-4xl opacity-30">{icon}</div>}
      <p className="font-medium text-muted">{title}</p>
      {children && <div className="mt-1.5 max-w-md text-[13px] leading-relaxed">{children}</div>}
    </div>
  )
}

export function Switch({
  checked,
  onCheckedChange,
  label,
  disabled,
}: {
  checked: boolean
  onCheckedChange: (v: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        'relative h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        checked ? 'bg-accent-strong' : 'bg-line',
      )}
    >
      <span className={cn('absolute top-0.5 left-0.5 size-4 rounded-full bg-white transition-transform', checked && 'translate-x-4')} />
    </button>
  )
}

export function PageHeader({ title, count, children }: { title: string; count?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <h1 className="text-base font-semibold">{title}</h1>
      {count != null && <span className="text-[13px] text-faint">{count}</span>}
      <div className="flex-1" />
      {children}
    </div>
  )
}
