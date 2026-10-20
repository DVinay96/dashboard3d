import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export const buttonVariants = cva(
  'inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-lg font-semibold transition-colors disabled:pointer-events-none disabled:opacity-45',
  {
    variants: {
      variant: {
        default: 'bg-accent-strong text-white hover:bg-accent-strong/85',
        outline: 'border border-line text-muted hover:bg-panel-2 hover:text-fg',
        ghost: 'text-muted hover:bg-panel-2 hover:text-fg',
        danger: 'border border-line text-muted hover:border-fail/40 hover:bg-fail/15 hover:text-fail',
      },
      size: { sm: 'h-8 px-3 text-[12.5px]', md: 'h-9 px-4 text-sm', icon: 'size-8' },
    },
    defaultVariants: { variant: 'default', size: 'md' },
  },
)

type Props = ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean; loading?: boolean }

export function Button({ className, variant, size, asChild, loading, children, disabled, ...props }: Props) {
  const Comp = asChild ? Slot : 'button'
  return (
    <Comp className={cn(buttonVariants({ variant, size }), className)} disabled={disabled || loading} {...props}>
      {asChild ? (
        children
      ) : (
        <>
          {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
          {children}
        </>
      )}
    </Comp>
  )
}
