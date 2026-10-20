import { useQuery } from '@tanstack/react-query'
import { Download, FolderKanban, RefreshCw, Trash2, Paintbrush, ScrollText } from 'lucide-react'
import { useState } from 'react'
import { fetchLog, useCatalog, useDeleteProduct, useRetexture, useRetry } from '@/api/queries'
import { ACTIVE_STATUSES, type FieldDef, type Product, type QaMetrics } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useConfirm } from '@/components/ui/confirm'
import { Textarea } from '@/components/ui/input'
import { useSession } from '@/lib/session'
import { AssignProjectsDialog } from './assign-projects-dialog'
import { QaReport } from './qa-report'
import { UnitySection } from './unity-section'

function MetadataTable({ product }: { product: Product }) {
  const s = useSession()
  const catalog = useCatalog(s.can('brands:read'))
  const entries = Object.entries(product.metadata ?? {})
  if (!entries.length) return null
  const labels: Record<string, string> = {}
  for (const f of (catalog.data?.base_fields ?? []) as FieldDef[]) labels[f.key] = f.label
  const brand = catalog.data?.brands.find((b) => b.id === product.brand_id)
  for (const f of (brand?.fields ?? []) as FieldDef[]) labels[f.key] = f.label
  const show = (v: unknown) => (v === true ? 'Sí' : v === false ? 'No' : String(v ?? '') || '—')
  return (
    <table className="w-full text-[12.5px]">
      <tbody>
        {product.brand_name && (
          <tr className="border-t border-line">
            <td className="w-1/3 py-1.5 text-muted">Marca</td>
            <td className="py-1.5 font-semibold">{product.brand_name}</td>
          </tr>
        )}
        {entries.map(([k, v]) => (
          <tr key={k} className="border-t border-line">
            <td className="w-1/3 py-1.5 text-muted">{labels[k] ?? k}</td>
            <td className="py-1.5">{show(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function LogViewer({ product }: { product: Product }) {
  const active = ACTIVE_STATUSES.includes(product.status)
  const log = useQuery({
    queryKey: ['log', product.id],
    queryFn: () => fetchLog(product.id),
    refetchInterval: active ? 2000 : false,
  })
  return (
    <pre className="max-h-64 overflow-auto rounded-lg border border-line bg-bg p-3 font-mono text-[11.5px] whitespace-pre-wrap text-muted">
      {log.data ?? 'Cargando…'}
    </pre>
  )
}

export function ProductDetail({ product: p }: { product: Product }) {
  const s = useSession()
  const confirm = useConfirm()
  const retry = useRetry()
  const del = useDeleteProduct()
  const retexture = useRetexture()
  const [retexOpen, setRetexOpen] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [showLog, setShowLog] = useState(false)
  const [assignOpen, setAssignOpen] = useState(false)

  const m = p.metrics as QaMetrics | null
  const active = ACTIVE_STATUSES.includes(p.status)

  const startRetexture = async () => {
    const ok = await confirm({
      title: 'Cambiar el material',
      description: 'Esto crea una tarea de re-texturizado y consume créditos del generador.',
      confirmLabel: 'Generar',
    })
    if (ok) retexture.mutate({ id: p.id, prompt: prompt.trim() }, { onSuccess: () => { setRetexOpen(false); setPrompt('') } })
  }

  const remove = async () => {
    const ok = await confirm({
      title: 'Borrar el producto',
      description: `Se borra “${p.name}” y todos sus archivos. No se puede deshacer.`,
      confirmLabel: 'Borrar',
      destructive: true,
    })
    if (ok) del.mutate(p.id)
  }

  return (
    <div className="space-y-4 border-t border-line pt-4">
      {p.error && (
        <div role="alert" className="rounded-lg border border-fail/30 bg-fail/10 px-3 py-2.5 text-[12.5px] text-[#ffadad]">
          <b>Error:</b> {p.error}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {m?.exported &&
          s.can('products:download') &&
          Object.entries(m.exported).map(([fmt, file]) => (
            <Button key={fmt} size="sm" asChild>
              <a href={`/api/products/${p.id}/files/out/${file}?download=1`}>
                <Download className="size-3.5" /> Descargar {fmt.toUpperCase()}
              </a>
            </Button>
          ))}
        {m && Boolean(p.raw_files?.glb) && s.can('products:retexture') && (
          <Button size="sm" variant="outline" onClick={() => setRetexOpen((v) => !v)} aria-expanded={retexOpen}>
            <Paintbrush className="size-3.5" /> Cambiar material
          </Button>
        )}
        {s.can('products:retry') && (
          <Button size="sm" variant="outline" disabled={active} loading={retry.isPending} onClick={() => retry.mutate(p.id)}>
            <RefreshCw className="size-3.5" /> Reprocesar
          </Button>
        )}
        {s.can('products:assign') && (
          <Button size="sm" variant="outline" onClick={() => setAssignOpen(true)}>
            <FolderKanban className="size-3.5" /> Proyectos
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={() => setShowLog((v) => !v)} aria-expanded={showLog}>
          <ScrollText className="size-3.5" /> Log
        </Button>
        {s.can('products:delete') && (
          <Button size="sm" variant="danger" disabled={active} onClick={remove}>
            <Trash2 className="size-3.5" /> Borrar
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5 text-xs text-faint">
        Proyectos:
        {p.projects.map((x) => (
          <Badge key={x.id}>{x.name}</Badge>
        ))}
        {p.created_by && <span className="ml-2">· creado por {p.created_by.display_name || p.created_by.email}</span>}
      </div>

      {retexOpen && (
        <div className="rounded-lg border border-line bg-bg p-3.5">
          <label htmlFor={`retex-${p.id}`} className="mb-1.5 block text-[11px] font-semibold tracking-wide text-faint uppercase">
            Nuevo material
          </label>
          <Textarea
            id={`retex-${p.id}`}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="cuero negro con textura granulada, acabado semimate; patas de metal negro mate"
            autoFocus
          />
          <p className="mt-1.5 text-xs text-faint">
            Vuelve a pintar esta misma geometría: la forma no cambia, solo la textura. Crea un producto nuevo y no toca
            este. Gasta créditos del generador.
          </p>
          <Button size="sm" className="mt-2.5" disabled={!prompt.trim()} loading={retexture.isPending} onClick={startRetexture}>
            Generar material
          </Button>
        </div>
      )}

      <UnitySection product={p} />

      <MetadataTable product={p} />

      {p.parent_id && (
        <p className="text-xs text-muted">
          Material re-generado desde otro producto con: <b>{p.retexture_prompt}</b>
        </p>
      )}

      <QaReport product={p} />
      {showLog && <LogViewer product={p} />}
      <AssignProjectsDialog product={p} open={assignOpen} onOpenChange={setAssignOpen} />
    </div>
  )
}
