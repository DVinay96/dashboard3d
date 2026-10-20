import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import type { FieldDef } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Checkbox, Input, Select } from '@/components/ui/input'

export const FIELD_TYPES: [FieldDef['type'], string][] = [
  ['text', 'Texto'],
  ['number', 'Número'],
  ['select', 'Lista'],
  ['bool', 'Sí / No'],
  ['date', 'Fecha'],
]

type Row = FieldDef & { optionsText: string }

const toRow = (f: FieldDef): Row => ({ ...f, optionsText: (f.options ?? []).join(', ') })
const fromRow = ({ optionsText, ...f }: Row): FieldDef => ({
  ...f,
  options: f.type === 'select' ? optionsText.split(',').map((o) => o.trim()).filter(Boolean) : [],
})

const blank = (): Row => ({ key: '', label: '', type: 'text', required: false, options: [], default: '', help: '', optionsText: '' })

export function FieldsEditor({ initial, onChange }: { initial: FieldDef[]; onChange: (fields: FieldDef[]) => void }) {
  const [rows, setRows] = useState<Row[]>(() => initial.map(toRow))

  const commit = (next: Row[]) => {
    setRows(next)
    onChange(next.map(fromRow))
  }
  const patch = (i: number, p: Partial<Row>) => commit(rows.map((r, j) => (j === i ? { ...r, ...p } : r)))

  return (
    <div>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={i} className="rounded-lg border border-line bg-bg p-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <Input
                aria-label="Nombre visible"
                className="min-w-40 flex-1"
                placeholder="Nombre visible"
                value={r.label}
                onChange={(e) => patch(i, { label: e.target.value })}
              />
              <Select aria-label="Tipo" className="w-28" value={r.type} onChange={(e) => patch(i, { type: e.target.value as FieldDef['type'] })}>
                {FIELD_TYPES.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </Select>
              <label className="flex items-center gap-1.5 text-xs text-muted">
                <Checkbox checked={r.required} onChange={(e) => patch(i, { required: e.target.checked })} /> Obligatorio
              </label>
              <Button type="button" size="icon" variant="danger" aria-label={`Quitar ${r.label || 'campo'}`} onClick={() => commit(rows.filter((_, j) => j !== i))}>
                <Trash2 className="size-3.5" />
              </Button>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {r.type === 'select' && (
                <Input
                  aria-label="Opciones"
                  placeholder="Opciones separadas por coma"
                  value={r.optionsText}
                  onChange={(e) => patch(i, { optionsText: e.target.value })}
                />
              )}
              {r.type === 'bool' ? (
                <label className="flex h-9 items-center gap-1.5 text-xs text-muted">
                  <Checkbox checked={r.default === true} onChange={(e) => patch(i, { default: e.target.checked })} /> Marcado por defecto
                </label>
              ) : (
                <Input aria-label="Valor por defecto" placeholder="Valor por defecto" value={String(r.default ?? '')} onChange={(e) => patch(i, { default: e.target.value })} />
              )}
              <Input aria-label="Ayuda" placeholder="Ayuda (opcional)" value={r.help} onChange={(e) => patch(i, { help: e.target.value })} className={r.type === 'select' ? '' : 'sm:col-span-2'} />
            </div>
            {r.key && <div className="mt-1.5 font-mono text-[11px] text-faint">clave: {r.key}</div>}
          </div>
        ))}
        {rows.length === 0 && <p className="py-2 text-[13px] text-faint">Sin campos.</p>}
      </div>
      <Button type="button" variant="outline" size="sm" className="mt-2.5" onClick={() => commit([...rows, blank()])}>
        <Plus className="size-3.5" /> Campo
      </Button>
    </div>
  )
}
