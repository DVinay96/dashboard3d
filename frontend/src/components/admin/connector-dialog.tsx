import { useState } from 'react'
import { useCreateIntegration, useSaveIntegration } from '@/api/queries'
import type { Integration, IntegrationEvent } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { CheckRow, Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { SecretInput } from './secret-input'

type Kind = 'mcp' | 'webhook'

function Form({ kind, integration, events, onDone }: { kind: Kind; integration?: Integration; events: IntegrationEvent[]; onDone: () => void }) {
  const create = useCreateIntegration()
  const save = useSaveIntegration()
  const secretField = kind === 'mcp' ? 'token' : 'signing_secret'
  const [name, setName] = useState(integration?.name ?? '')
  const [url, setUrl] = useState(String(integration?.config.url ?? ''))
  const [tool, setTool] = useState(String(integration?.config.event_tool ?? ''))
  const [secret, setSecret] = useState('')
  const [selected, setSelected] = useState<string[]>((integration?.config.events as string[] | undefined) ?? [])
  const config = { url, events: selected, ...(kind === 'mcp' ? { event_tool: tool } : {}) }
  const secrets = secret ? { [secretField]: secret } : {}

  const submit = () =>
    integration
      ? save.mutate({ id: integration.id, body: { name, config, secrets } }, { onSuccess: onDone })
      : create.mutate({ kind, name, config, secrets }, { onSuccess: onDone })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <div className="grid gap-x-4 sm:grid-cols-2">
        <Field label="Nombre">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required autoFocus />}</Field>
        <Field label={kind === 'mcp' ? 'URL del servidor MCP' : 'URL de destino'}>
          {(id) => <Input id={id} type="url" className="font-mono" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" required />}
        </Field>
      </div>
      <SecretInput
        label={kind === 'mcp' ? 'Token (Bearer)' : 'Secreto de firma'}
        state={integration?.secrets[secretField]}
        value={secret}
        onChange={setSecret}
        hint={kind === 'webhook' ? 'Con él se firma cada entrega en la cabecera X-Pipeline-Signature (HMAC SHA-256).' : undefined}
      />
      {kind === 'mcp' && (
        <Field label="Herramienta que recibe los eventos (opcional)" hint="Se la invoca con { event, payload } cada vez que ocurre uno de los eventos elegidos.">
          {(id) => <Input id={id} className="font-mono" value={tool} onChange={(e) => setTool(e.target.value)} placeholder="on_event" />}
        </Field>
      )}
      <Field label="Eventos">
        {() => (
          <div className="rounded-lg border border-line p-2.5">
            {events.map((e) => (
              <CheckRow
                key={e.name}
                checked={selected.includes(e.name)}
                onChange={(on) => setSelected(on ? [...selected, e.name] : selected.filter((x) => x !== e.name))}
                label={<span className="font-mono text-xs">{e.name}</span>}
                description={e.description}
              />
            ))}
          </div>
        )}
      </Field>
      <DialogFooter>
        <Button type="submit" loading={create.isPending || save.isPending} disabled={!name.trim() || !url.trim()}>
          Guardar
        </Button>
      </DialogFooter>
    </form>
  )
}

export function ConnectorDialog({
  kind,
  integration,
  events,
  open,
  onOpenChange,
}: {
  kind: Kind
  integration?: Integration
  events: IntegrationEvent[]
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const title = integration ? `Editar ${integration.name}` : kind === 'mcp' ? 'Conectar servidor MCP' : 'Agregar webhook'
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <DialogContent title={title} className="max-w-xl">
          <Form kind={kind} integration={integration} events={events} onDone={() => onOpenChange(false)} />
        </DialogContent>
      )}
    </Dialog>
  )
}
