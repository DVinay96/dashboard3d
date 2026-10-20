import { useState } from 'react'
import { useAssignProjects } from '@/api/queries'
import type { Product } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { ProjectPicker } from './project-picker'

function Body({ product, onClose }: { product: Product; onClose: () => void }) {
  const [ids, setIds] = useState(product.projects.map((p) => p.id))
  const assign = useAssignProjects()
  return (
    <>
      <ProjectPicker value={ids} onChange={setIds} />
      <DialogFooter className="mt-4">
        <Button variant="outline" onClick={onClose}>
          Cancelar
        </Button>
        <Button
          loading={assign.isPending}
          disabled={!ids.length}
          onClick={() => assign.mutate({ id: product.id, projectIds: ids }, { onSuccess: onClose })}
        >
          Guardar
        </Button>
      </DialogFooter>
    </>
  )
}

export function AssignProjectsDialog({ product, open, onOpenChange }: { product: Product; open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <DialogContent title="Proyectos del producto" description={`“${product.name}” aparece en cada proyecto que marques.`}>
          <Body product={product} onClose={() => onOpenChange(false)} />
        </DialogContent>
      )}
    </Dialog>
  )
}
