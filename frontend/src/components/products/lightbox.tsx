import { createContext, useContext, useState, type ReactNode } from 'react'
import { Dialog, DialogContent } from '@/components/ui/dialog'

const LightboxContext = createContext<(src: string, caption?: string) => void>(() => {})
export const useLightbox = () => useContext(LightboxContext)

export function LightboxProvider({ children }: { children: ReactNode }) {
  const [shot, setShot] = useState<{ src: string; caption?: string } | null>(null)
  return (
    <LightboxContext.Provider value={(src, caption) => setShot({ src, caption })}>
      {children}
      <Dialog open={!!shot} onOpenChange={(o) => !o && setShot(null)}>
        {shot && (
          <DialogContent title={shot.caption ?? 'Imagen'} className="max-w-4xl">
            <img src={shot.src} alt={shot.caption ?? ''} className="mx-auto max-h-[75vh] rounded-lg" />
          </DialogContent>
        )}
      </Dialog>
    </LightboxContext.Provider>
  )
}
