import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import type { ModuleInfo, Project, Statement } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/field'
import { Select, Textarea } from '@/components/ui/input'
import { emptyStatement, parseLines, projectResources } from '@/lib/iam'

interface Row {
  effect: Statement['effect']
  actionsText: string
  resourcesText: string
}

const toRow = (s: Statement): Row => ({ effect: s.effect, actionsText: s.actions.join('\n'), resourcesText: s.resources.join('\n') })
const fromRow = (r: Row): Statement => ({ effect: r.effect, actions: parseLines(r.actionsText), resources: parseLines(r.resourcesText) })
const append = (text: string, line: string) => (text && !text.endsWith('\n') ? `${text}\n${line}` : text + line)

export function StatementEditor({
  initial,
  modules,
  projects,
  onChange,
}: {
  initial: Statement[]
  modules: ModuleInfo[]
  projects: Project[]
  onChange: (s: Statement[]) => void
}) {
  const [rows, setRows] = useState<Row[]>(() => initial.map(toRow))
  const [active, setActive] = useState(0)
  const families = [...new Set(modules.flatMap((m) => m.actions.map((a) => a.name.split(':')[0]!)))]

  const commit = (next: Row[]) => {
    setRows(next)
    onChange(next.map(fromRow))
  }
  const patch = (i: number, p: Partial<Row>) => commit(rows.map((r, j) => (j === i ? { ...r, ...p } : r)))
  const addToActive = (field: 'actionsText' | 'resourcesText', ...lines: string[]) => {
    const i = Math.min(active, rows.length - 1)
    const row = rows[i]
    if (row) patch(i, { [field]: lines.reduce(append, row[field]) })
  }

  return (
    <div>
      {rows.map((r, i) => (
        <div key={i} className={`mb-2.5 rounded-lg border bg-bg p-3 ${i === active ? 'border-accent/50' : 'border-line'}`}>
          <div className="mb-2.5 flex items-center gap-2">
            <Select aria-label={`Efecto del statement ${i + 1}`} className="w-28" value={r.effect} onChange={(e) => patch(i, { effect: e.target.value as Row['effect'] })}>
              <option value="allow">Allow</option>
              <option value="deny">Deny</option>
            </Select>
            <span className="flex-1 text-xs text-faint">Statement {i + 1}</span>
            <Button type="button" size="icon" variant="danger" aria-label={`Quitar statement ${i + 1}`} onClick={() => commit(rows.filter((_, j) => j !== i))}>
              <Trash2 className="size-3.5" />
            </Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor={`act-${i}`}>Acciones (una por línea)</Label>
              <Textarea id={`act-${i}`} className="font-mono text-xs" placeholder="products:read" value={r.actionsText} onFocus={() => setActive(i)} onChange={(e) => patch(i, { actionsText: e.target.value })} />
            </div>
            <div>
              <Label htmlFor={`res-${i}`}>Recursos (una por línea)</Label>
              <Textarea id={`res-${i}`} className="font-mono text-xs" placeholder="*" value={r.resourcesText} onFocus={() => setActive(i)} onChange={(e) => patch(i, { resourcesText: e.target.value })} />
            </div>
          </div>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={() => commit([...rows, toRow(emptyStatement())])}>
        <Plus className="size-3.5" /> Statement
      </Button>

      <details className="mt-4 rounded-lg border border-line" open>
        <summary className="cursor-pointer px-3 py-2 text-[13px] font-medium text-muted">Agregar al statement {Math.min(active, rows.length - 1) + 1}</summary>
        <div className="space-y-3 border-t border-line p-3">
          <div>
            <div className="mb-1 text-[11px] font-semibold tracking-wide text-faint uppercase">Comodines</div>
            <div className="flex flex-wrap gap-1.5">
              <Chip title="Todas las acciones" onClick={() => addToActive('actionsText', '*')}>
                * (todas)
              </Chip>
              {families.map((f) => (
                <Chip key={f} title={`Toda la familia ${f}`} onClick={() => addToActive('actionsText', `${f}:*`)}>
                  {f}:*
                </Chip>
              ))}
            </div>
          </div>
          {modules.map((m) => (
            <div key={m.id}>
              <div className="mb-1 text-[11px] font-semibold tracking-wide text-faint uppercase">{m.label}</div>
              <div className="flex flex-wrap gap-1.5">
                {m.actions.map((a) => (
                  <Chip key={a.name} title={a.description} onClick={() => addToActive('actionsText', a.name)}>
                    {a.name}
                  </Chip>
                ))}
              </div>
            </div>
          ))}
          <div>
            <div className="mb-1 text-[11px] font-semibold tracking-wide text-faint uppercase">Recursos</div>
            <div className="flex flex-wrap gap-1.5">
              <Chip title="Todo" onClick={() => addToActive('resourcesText', '*')}>
                * (todo)
              </Chip>
              {projects.map((p) => (
                <Chip key={p.id} title={`Solo el proyecto ${p.name}`} onClick={() => addToActive('resourcesText', ...projectResources(p.id))}>
                  Proyecto: {p.name}
                </Chip>
              ))}
            </div>
            <p className="mt-2 text-xs leading-relaxed text-faint">
              Formatos: <code>project/&lt;id&gt;</code>, <code>project/&lt;id&gt;/*</code> (sus productos), <code>brand/&lt;id&gt;</code>,{' '}
              <code>brand/none</code>, <code>schema/base</code>. Un <code>deny</code> siempre gana; lo no permitido queda prohibido.
            </p>
          </div>
        </div>
      </details>
    </div>
  )
}

function Chip({ children, title, onClick }: { children: React.ReactNode; title: string; onClick: () => void }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="cursor-pointer rounded-full border border-line bg-panel px-2.5 py-0.5 font-mono text-[11.5px] text-muted hover:border-accent hover:text-fg"
    >
      {children}
    </button>
  )
}
