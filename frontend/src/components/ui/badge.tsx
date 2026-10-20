import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = cva('inline-flex items-center gap-1 rounded-full border px-2 py-px text-[11.5px] font-medium whitespace-nowrap', {
  variants: {
    tone: {
      neutral: 'border-line bg-panel-2 text-muted',
      accent: 'border-accent/30 bg-accent/10 text-accent',
      ok: 'border-ok/30 bg-ok/10 text-ok',
      warn: 'border-warn/30 bg-warn/10 text-warn',
      fail: 'border-fail/30 bg-fail/10 text-fail',
    },
  },
  defaultVariants: { tone: 'neutral' },
})

export function Badge({ className, tone, ...props }: ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
