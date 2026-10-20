import { createFileRoute } from "@tanstack/react-router";
import { Building2, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import {
  useClients,
  useCreateClient,
  useDeleteClient,
  useUpdateClient,
} from "@/api/queries";
import type { Client } from "@/api/types";
import { ModuleToggles } from "@/components/admin/module-toggles";
import { SuperGate } from "@/components/layout/guards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { EmptyState, PageHeader, Skeleton, Switch } from "@/components/ui/misc";
import { setIdentity } from "@/lib/identity";

export const Route = createFileRoute("/admin/clients")({
  component: () => (
    <SuperGate>
      <ClientsPage />
    </SuperGate>
  ),
});

const DEFAULT_MODULES = ["catalog", "generation", "brands"];

function ClientForm({
  client,
  onDone,
}: {
  client?: Client;
  onDone: () => void;
}) {
  const create = useCreateClient();
  const update = useUpdateClient();
  const [name, setName] = useState(client?.name ?? "");
  const [accent, setAccent] = useState(
    (client?.theme.accent as string | undefined) ?? "",
  );
  const [logo, setLogo] = useState(
    (client?.theme.logo_url as string | undefined) ?? "",
  );
  const [modules, setModules] = useState(client?.modules ?? DEFAULT_MODULES);
  const theme = {
    ...(accent ? { accent } : {}),
    ...(logo.trim() ? { logo_url: logo.trim() } : {}),
  };

  const submit = () =>
    client
      ? update.mutate(
          { id: client.id, body: { name, theme } },
          { onSuccess: onDone },
        )
      : create.mutate({ name, theme, modules }, { onSuccess: onDone });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <Field label="Nombre">
        {(id) => (
          <Input
            id={id}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
          />
        )}
      </Field>
      <div className="grid gap-x-4 sm:grid-cols-[8rem_1fr]">
        <Field label="Color de acento">
          {(id) => (
            <div className="flex items-center gap-2">
              <input
                id={id}
                type="color"
                value={accent || "#5b9dff"}
                onChange={(e) => setAccent(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded-lg border border-line bg-bg p-1"
              />
              {accent && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setAccent("")}
                >
                  Quitar
                </Button>
              )}
            </div>
          )}
        </Field>
        <Field label="Logo (URL)">
          {(id) => (
            <Input
              id={id}
              value={logo}
              onChange={(e) => setLogo(e.target.value)}
              placeholder="https://…/logo.png"
            />
          )}
        </Field>
      </div>
      {!client && (
        <Field
          label="Módulos"
          hint="Se pueden cambiar después, en cualquier momento."
        >
          {() => <ModuleToggles value={modules} onChange={setModules} />}
        </Field>
      )}
      <DialogFooter>
        <Button
          type="submit"
          loading={create.isPending || update.isPending}
          disabled={!name.trim()}
        >
          {client ? "Guardar" : "Crear cliente"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function ClientsPage() {
  const clients = useClients();
  const update = useUpdateClient();
  const del = useDeleteClient();
  const confirm = useConfirm();
  const [editing, setEditing] = useState<Client | "new" | null>(null);

  const operate = (c: Client) => {
    setIdentity({ actAs: null, clientId: c.id });
    window.location.assign("/products");
  };
  const remove = async (c: Client) => {
    if (
      await confirm({
        title: "Borrar el cliente",
        description: `Se borra “${c.name}” con sus usuarios, proyectos y marcas. Solo se puede si no tiene productos.`,
        confirmLabel: "Borrar",
        destructive: true,
      })
    )
      del.mutate(c.id);
  };

  return (
    <>
      <PageHeader
        title="Clientes"
        count={clients.data ? `${clients.data.length} en total` : undefined}
      >
        <Button size="sm" onClick={() => setEditing("new")}>
          <Plus className="size-4" /> Nuevo cliente
        </Button>
      </PageHeader>

      {clients.isPending ? (
        <Skeleton className="h-40" />
      ) : clients.isError ? (
        <EmptyState title="No se pudieron cargar los clientes">
          {clients.error.message}
        </EmptyState>
      ) : clients.data.length === 0 ? (
        <EmptyState
          icon={<Building2 className="mx-auto size-10" />}
          title="Todavía no hay clientes"
        >
          Crea el primero: cada cliente tiene sus propios usuarios, proyectos,
          marcas y productos, y accede solo a los módulos que le habilites.
        </EmptyState>
      ) : (
        <div className="grid gap-3.5 lg:grid-cols-2">
          {clients.data.map((c) => (
            <Card key={c.id} className={c.disabled ? "opacity-70" : undefined}>
              <CardBody>
                <div className="mb-3 flex items-start gap-2">
                  <span
                    className="mt-0.5 size-3 shrink-0 rounded-full"
                    style={{
                      background:
                        (c.theme.accent as string | undefined) ??
                        "var(--color-accent)",
                    }}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <h2 className="truncate text-[15px] font-semibold">
                      {c.name}
                    </h2>
                    <p className="text-xs text-faint">
                      {c.user_count} usuarios · {c.project_count} proyectos ·{" "}
                      {c.product_count} productos
                    </p>
                  </div>
                  {c.disabled && <Badge tone="fail">deshabilitado</Badge>}
                </div>
                <div className="mb-3 rounded-lg border border-line bg-bg p-3">
                  <div className="mb-2 text-[11px] font-semibold tracking-wide text-faint uppercase">
                    Módulos
                  </div>
                  <ModuleToggles
                    value={c.modules}
                    onChange={(modules) =>
                      update.mutate({ id: c.id, body: { modules } })
                    }
                  />
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => operate(c)}
                    disabled={c.disabled}
                  >
                    <Play className="size-3.5" /> Operar como este cliente
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Editar ${c.name}`}
                    onClick={() => setEditing(c)}
                  >
                    <Pencil className="size-3.5" />
                  </Button>
                  <span className="ml-auto flex items-center gap-2 text-xs text-muted">
                    Activo
                    <Switch
                      label={`Cliente ${c.name} activo`}
                      checked={!c.disabled}
                      onCheckedChange={(on) =>
                        update.mutate({ id: c.id, body: { disabled: !on } })
                      }
                    />
                  </span>
                  <Button
                    size="icon"
                    variant="danger"
                    aria-label={`Borrar ${c.name}`}
                    onClick={() => remove(c)}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        {editing && (
          <DialogContent
            title={
              editing === "new" ? "Nuevo cliente" : `Editar ${editing.name}`
            }
          >
            <ClientForm
              client={editing === "new" ? undefined : editing}
              onDone={() => setEditing(null)}
            />
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
