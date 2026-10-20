import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Label({ className, ...props }: React.ComponentProps<'label'>) {
  return <label className={cn('mb-1.5 block text-[11px] font-semibold tracking-wide text-faint uppercase', className)} {...props} />
}

export function Field({
  label,
  hint,
  error,
  className,
  children,
}: {
  label: ReactNode
  hint?: ReactNode
  error?: string | null
  className?: string
  children: (id: string) => ReactNode
}) {
  const id = useId()
  return (
    <div className={cn('mb-4', className)}>
      <Label htmlFor={id}>{label}</Label>
      {children(id)}
      {hint && <p className="mt-1.5 text-xs leading-relaxed text-faint">{hint}</p>}
      {error && (
        <p role="alert" className="mt-1.5 text-xs text-fail">
          {error}
        </p>
      )}
    </div>
  )
}

export function CheckRow({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: ReactNode
  description?: ReactNode
  disabled?: boolean
}) {
  return (
    <label className={cn('my-1.5 flex cursor-pointer items-start gap-2.5', disabled && 'cursor-not-allowed opacity-50')}>
      <input
        type="checkbox"
        className="mt-0.5 size-4 shrink-0 cursor-pointer accent-accent"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="text-[13px] leading-snug">
        {label}
        {description && <small className="mt-0.5 block text-xs text-faint">{description}</small>}
      </span>
    </label>
  )
}
