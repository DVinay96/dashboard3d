import * as T from '@radix-ui/react-tabs'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export const Tabs = T.Root

export function TabsList({ className, ...props }: ComponentProps<typeof T.List>) {
  return <T.List className={cn('mb-4 flex gap-1', className)} {...props} />
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        'cursor-pointer rounded-lg border border-transparent px-3.5 py-1.5 font-semibold text-faint hover:bg-panel-2 hover:text-fg data-[state=active]:border-line data-[state=active]:bg-panel-2 data-[state=active]:text-fg',
        className,
      )}
      {...props}
    />
  )
}

export const TabsContent = T.Content
