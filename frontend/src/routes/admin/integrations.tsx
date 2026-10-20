import { createFileRoute } from "@tanstack/react-router";
import { Pencil, Plug, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import {
  useDeleteIntegration,
  useIntegrations,
  useSaveIntegration,
  useTestIntegration,
} from "@/api/queries";
import type { Integration, IntegrationEvent } from "@/api/types";
import { ApiCard } from "@/components/admin/api-card";
import { ConnectorDialog } from "@/components/admin/connector-dialog";
import { IntegrationStatus } from "@/components/admin/integration-status";
import { SuperGate } from "@/components/layout/guards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm";
import { EmptyState, PageHeader, Skeleton, Switch } from "@/components/ui/misc";

export const Route = createFileRoute("/admin/integrations")({
  component: () => (
    <SuperGate>
      <IntegrationsPage />
    </SuperGate>
  ),
});

function ConnectorCard({
  integration: i,
  events,
  onEdit,
}: {
  integration: Integration;
  events: IntegrationEvent[];
  onEdit: () => void;
}) {
  const save = useSaveIntegration();
  const test = useTestIntegration();
  const del = useDeleteIntegration();
  const confirm = useConfirm();
  const subscribed = (i.config.events as string[] | undefined) ?? [];
  const remove = async () => {
    if (
      await confirm({
        title: "Borrar el conector",
        description: `Se borra “${i.name}” y deja de recibir eventos.`,
        confirmLabel: "Borrar",
        destructive: true,
      })
    )
      del.mutate(i.id);
  };
  return (
    <Card>
      <CardBody>
        <div className="mb-1 flex items-center gap-2">
          <h3 className="min-w-0 flex-1 truncate font-semibold">{i.name}</h3>
          <Badge tone={i.kind === "mcp" ? "accent" : "neutral"}>
            {i.kind === "mcp" ? "MCP" : "Webhook"}
          </Badge>
          <Switch
            label={`${i.name} activo`}
            checked={i.enabled}
            onCheckedChange={(on) =>
              save.mutate({ id: i.id, body: { enabled: on } })
            }
          />
        </div>
        <p className="mb-2 truncate font-mono text-xs text-faint">
          {String(i.config.url ?? "")}
        </p>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {subscribed.length === 0 && (
            <span className="text-xs text-faint">Sin eventos elegidos.</span>
          )}
          {subscribed.map((e) => (
            <Badge
              key={e}
              title={events.find((x) => x.name === e)?.description}
            >
              {e}
            </Badge>
          ))}
        </div>
        <div className="mb-3">
          <IntegrationStatus integration={i} configured />
        </div>
        <div className="flex gap-1.5">
          <Button
            size="sm"
            variant="outline"
            loading={test.isPending && test.variables === i.id}
            onClick={() => test.mutate(i.id)}
          >
            Probar conexión
          </Button>
          <Button
            size="icon"
            variant="ghost"
            aria-label={`Editar ${i.name}`}
            onClick={onEdit}
          >
            <Pencil className="size-3.5" />
          </Button>
          <Button
            size="icon"
            variant="danger"
            aria-label={`Borrar ${i.name}`}
            onClick={remove}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function IntegrationsPage() {
  const integrations = useIntegrations();
  const [dialog, setDialog] = useState<{
    kind: "mcp" | "webhook";
    integration?: Integration;
  } | null>(null);

  if (integrations.isPending) return <Skeleton className="h-64" />;
  if (integrations.isError)
    return (
      <EmptyState title="No se pudieron cargar las integraciones">
        {integrations.error.message}
      </EmptyState>
    );

  const { items, events } = integrations.data;
  const apis = items.filter((i) => i.kind === "meshy" || i.kind === "unity");
  const connectors = items.filter(
    (i) => i.kind === "mcp" || i.kind === "webhook",
  );
  const descriptions: Record<string, string> = {
    meshy:
      "Genera los modelos 3D a partir de las fotos. Se usa en Generación 3D.",
    unity:
      "Cuenta de servicio de la plataforma: publica los productos en el Asset Manager de Unity, en los proyectos que vincules.",
  };

  return (
    <>
      <PageHeader title="Integraciones" />
      <p className="mb-5 max-w-3xl text-[13px] text-muted">
        Aca se conecta todo lo externo. Las credenciales se guardan cifradas y
        no se vuelven a mostrar. Los conectores MCP y los webhooks reciben los
        eventos de la plataforma (un producto terminó, se publicó en Unity, algo
        falló) para que tus agentes puedan reaccionar.
      </p>

      <h2 className="mb-2.5 text-xs font-semibold tracking-wider text-faint uppercase">
        APIs
      </h2>
      <div className="mb-8 grid gap-3.5 lg:grid-cols-2">
        {apis.map((i) => (
          <ApiCard
            key={i.id + i.last_at}
            integration={i}
            description={descriptions[i.kind]}
          />
        ))}
      </div>

      <div className="mb-2.5 flex items-center gap-3">
        <h2 className="flex-1 text-xs font-semibold tracking-wider text-faint uppercase">
          MCP, agentes y webhooks
        </h2>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setDialog({ kind: "webhook" })}
        >
          <Plus className="size-4" /> Webhook
        </Button>
        <Button size="sm" onClick={() => setDialog({ kind: "mcp" })}>
          <Plus className="size-4" /> Servidor MCP
        </Button>
      </div>
      {connectors.length === 0 ? (
        <EmptyState
          icon={<Plug className="mx-auto size-10" />}
          title="Todavía no hay conectores"
        >
          Conecta un servidor MCP o un webhook para que tus agentes reciban los
          eventos de la plataforma.
        </EmptyState>
      ) : (
        <div className="grid gap-3.5 lg:grid-cols-2">
          {connectors.map((i) => (
            <ConnectorCard
              key={i.id}
              integration={i}
              events={events}
              onEdit={() =>
                setDialog({ kind: i.kind as "mcp" | "webhook", integration: i })
              }
            />
          ))}
        </div>
      )}

      {dialog && (
        <ConnectorDialog
          key={dialog.integration?.id ?? dialog.kind}
          kind={dialog.kind}
          integration={dialog.integration}
          events={events}
          open
          onOpenChange={(o) => !o && setDialog(null)}
        />
      )}
    </>
  );
}
