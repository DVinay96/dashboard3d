import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

export function SecretInput({
  label,
  state,
  value,
  onChange,
  hint,
}: {
  label: string
  state?: { set: boolean; hint: string }
  value: string
  onChange: (v: string) => void
  hint?: string
}) {
  return (
    <Field
      label={label}
      hint={
        state?.set
          ? `Guardada (${state.hint}). Dejalo vacío para conservarla; escribí otra para reemplazarla.${hint ? ' ' + hint : ''}`
          : hint
      }
    >
      {(id) => (
        <Input
          id={id}
          type="password"
          autoComplete="new-password"
          className="font-mono"
          value={value}
          placeholder={state?.set ? '••••••••' : ''}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </Field>
  )
}
