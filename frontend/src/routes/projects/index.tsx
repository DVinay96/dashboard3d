import { createFileRoute } from '@tanstack/react-router'
import { Archive, ArchiveRestore, FolderKanban, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useCreateProject, useDeleteProject, useProjects, useUpdateProject } from '@/api/queries'
import type { Project } from '@/api/types'
import { TenantGate } from '@/components/layout/guards'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardBody } from '@/components/ui/card'
import { useConfirm } from '@/components/ui/confirm'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { EmptyState, PageHeader, Skeleton } from '@/components/ui/misc'
import { useSession } from '@/lib/session'
import { Link } from '@tanstack/react-router'

export const Route = createFileRoute('/projects/')({
  component: () => (
    <TenantGate action="projects:read">
      <ProjectsPage />
    </TenantGate>
  ),
})

function ProjectForm({ project, onDone }: { project?: Project; onDone: () => void }) {
  const s = useSession()
  const create = useCreateProject()
  const update = useUpdateProject()
  const [name, setName] = useState(project?.name ?? '')
  const [description, setDescription] = useState(project?.description ?? '')
  const [unity, setUnity] = useState(project?.unity_project_id ?? '')
  const pending = create.isPending || update.isPending

  const submit = () => {
    if (!project) return create.mutate({ name, description }, { onSuccess: onDone })
    const body = { name, description, ...(s.isSuper ? { unity_project_id: unity.trim() || null } : {}) }
    update.mutate({ id: project.id, body }, { onSuccess: onDone })
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <Field label="Nombre">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required autoFocus />}</Field>
      <Field label="Descripción">
        {(id) => <Textarea id={id} value={description} onChange={(e) => setDescription(e.target.value)} />}
      </Field>
      {s.isSuper && project && (
        <Field label="ID del proyecto en Unity" hint="Destino en el Asset Manager de Unity. Solo lo define la plataforma.">
          {(id) => <Input id={id} value={unity} onChange={(e) => setUnity(e.target.value)} className="font-mono" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />}
        </Field>
      )}
      <DialogFooter>
        <Button type="submit" loading={pending} disabled={!name.trim()}>
          Guardar
        </Button>
      </DialogFooter>
    </form>
  )
}

function ProjectsPage() {
  const s = useSession()
  const projects = useProjects()
  const update = useUpdateProject()
  const del = useDeleteProject()
  const confirm = useConfirm()
  const [editing, setEditing] = useState<Project | 'new' | null>(null)

  const remove = async (p: Project) => {
    if (await confirm({ title: 'Borrar el proyecto', description: `Se borra “${p.name}”.`, confirmLabel: 'Borrar', destructive: true }))
      del.mutate(p.id)
  }

  return (
    <>
      <PageHeader title="Proyectos" count={projects.data ? `${projects.data.length} en total` : undefined}>
        {s.can('projects:create') && (
          <Button size="sm" onClick={() => setEditing('new')}>
            <Plus className="size-4" /> Nuevo proyecto
          </Button>
        )}
      </PageHeader>

      {projects.isPending ? (
        <Skeleton className="h-32" />
      ) : projects.isError ? (
        <EmptyState title="No se pudieron cargar los proyectos">{projects.error.message}</EmptyState>
      ) : projects.data.length === 0 ? (
        <EmptyState icon={<FolderKanban className="mx-auto size-10" />} title="No hay proyectos" />
      ) : (
        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data.map((p) => (
            <Card key={p.id} className={p.archived ? 'opacity-60' : undefined}>
              <CardBody>
                <div className="mb-1 flex items-start gap-2">
                  <h2 className="min-w-0 flex-1 truncate font-semibold">{p.name}</h2>
                  {p.archived && <Badge>archivado</Badge>}
                  {p.unity_project_id && <Badge tone="accent">Unity</Badge>}
                </div>
                <p className="mb-3 min-h-9 text-[12.5px] text-muted">{p.description || 'Sin descripción'}</p>
                <div className="flex items-center gap-1.5">
                  <Link to="/products" search={{ project: p.id }} className="mr-auto text-[13px] text-accent hover:underline">
                    {p.product_count} producto{p.product_count === 1 ? '' : 's'}
                  </Link>
                  {s.can('projects:update') && (
                    <>
                      <Button size="icon" variant="ghost" aria-label={`Editar ${p.name}`} onClick={() => setEditing(p)}>
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={p.archived ? `Desarchivar ${p.name}` : `Archivar ${p.name}`}
                        onClick={() => update.mutate({ id: p.id, body: { archived: !p.archived } })}
                      >
                        {p.archived ? <ArchiveRestore className="size-3.5" /> : <Archive className="size-3.5" />}
                      </Button>
                    </>
                  )}
                  {s.can('projects:delete') && (
                    <Button size="icon" variant="danger" aria-label={`Borrar ${p.name}`} onClick={() => remove(p)}>
                      <Trash2 className="size-3.5" />
                    </Button>
                  )}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        {editing && (
          <DialogContent title={editing === 'new' ? 'Nuevo proyecto' : `Editar ${editing.name}`}>
            <ProjectForm project={editing === 'new' ? undefined : editing} onDone={() => setEditing(null)} />
          </DialogContent>
        )}
      </Dialog>
    </>
  )
}
