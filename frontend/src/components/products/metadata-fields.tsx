import { Badge } from '@/components/ui/badge'
import { Checkbox, Input, Select } from '@/components/ui/input'
import { Field } from '@/components/ui/field'
import type { FieldDef } from '@/api/types'

export type MetaValues = Record<string, string | boolean>

export function defaultsFor(fields: FieldDef[]): MetaValues {
  const out: MetaValues = {}
  for (const f of fields) out[f.key] = f.type === 'bool' ? Boolean(f.default) : String(f.default ?? '')
  return out
}

export function MetadataFields({
  fields,
  values,
  onChange,
}: {
  fields: FieldDef[]
  values: MetaValues
  onChange: (key: string, value: string | boolean) => void
}) {
  if (!fields.length)
    return <p className="text-xs text-faint">Sin campos definidos. Configuralos en Marcas.</p>
  return (
    <div className="grid gap-x-3 sm:grid-cols-2">
      {fields.map((f) => (
        <Field
          key={f.key}
          className="mb-3"
          label={
            <>
              {f.label}
              {f.required && <span className="text-fail"> *</span>}
              {f.scope === 'brand' && (
                <Badge tone="accent" className="ml-1.5 align-middle normal-case">
                  marca
                </Badge>
              )}
            </>
          }
        >
          {(id) => {
            const v = values[f.key]
            if (f.type === 'bool')
              return (
                <label className="flex h-9 items-center gap-2">
                  <Checkbox id={id} checked={v === true} onChange={(e) => onChange(f.key, e.target.checked)} /> Sí
                </label>
              )
            if (f.type === 'select')
              return (
                <Select id={id} value={String(v ?? '')} onChange={(e) => onChange(f.key, e.target.value)}>
                  {!f.required && <option value="" />}
                  {f.options.map((o) => (
                    <option key={o}>{o}</option>
                  ))}
                </Select>
              )
            return (
              <Input
                id={id}
                type={f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
                value={String(v ?? '')}
                placeholder={f.help}
                onChange={(e) => onChange(f.key, e.target.value)}
              />
            )
          }}
        </Field>
      ))}
    </div>
  )
}
