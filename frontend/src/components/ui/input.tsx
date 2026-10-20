import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

const control =
  'w-full rounded-lg border border-line bg-bg px-3 text-sm text-fg outline-none transition-colors focus:border-accent disabled:opacity-50'

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input className={cn(control, 'h-9', className)} {...props} />
}

export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return <textarea className={cn(control, 'min-h-16 resize-y py-2', className)} {...props} />
}

export function Select({ className, ...props }: ComponentProps<'select'>) {
  return <select className={cn(control, 'h-9 cursor-pointer', className)} {...props} />
}

export function Checkbox({ className, ...props }: Omit<ComponentProps<'input'>, 'type'>) {
  return <input type="checkbox" className={cn('size-4 shrink-0 cursor-pointer accent-accent', className)} {...props} />
}
