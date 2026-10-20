import { useModules } from '@/api/queries'
import { Switch } from '@/components/ui/misc'

export function ModuleToggles({
  value,
  onChange,
  disabled,
}: {
  value: string[]
  onChange: (modules: string[]) => void
  disabled?: boolean
}) {
  const modules = useModules()
  return (
    <ul className="space-y-2.5">
      {(modules.data ?? []).map((m) => (
        <li key={m.id} className="flex items-start gap-3">
          <Switch
            label={m.label}
            checked={value.includes(m.id)}
            disabled={disabled}
            onCheckedChange={(on) => onChange(on ? [...value, m.id] : value.filter((x) => x !== m.id))}
          />
          <div className="min-w-0 text-[13px] leading-snug">
            <b className="font-semibold">{m.label}</b>
            <p className="text-xs text-faint">{m.description}</p>
          </div>
        </li>
      ))}
    </ul>
  )
}
