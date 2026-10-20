import { createFileRoute } from "@tanstack/react-router";
import { CircleAlert, CloudUpload } from "lucide-react";
import { useUnityStatus, useUnitySync } from "@/api/queries";
import { TenantGate } from "@/components/layout/guards";
import { UnityStatusBadge } from "@/components/products/unity-status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { fmtDate } from "@/lib/format";
import { useSession } from "@/lib/session";

export const Route = createFileRoute("/unity/")({
  component: () => (
    <TenantGate action="unity:read">
      <UnityPage />
    </TenantGate>
  ),
});

function UnityPage() {
  const s = useSession();
  const status = useUnityStatus();
  const sync = useUnitySync();

  return (
    <>
      <PageHeader
        title="Sincronización con Unity"
        count={
          status.data ? `${status.data.items.length} publicaciones` : undefined
        }
      />
      {status.data && !status.data.configured && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-2.5 rounded-lg border border-warn/30 bg-warn/10 px-3.5 py-3 text-[13px] text-warn"
        >
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <span>
            Todavía no esta conectada la cuenta de servicio de Unity. El
            administrador la conecta en Integraciones; hasta entonces no se
            puede publicar.
          </span>
        </div>
      )}
      <p className="mb-4 max-w-3xl text-[13px] text-muted">
        Cada producto terminado se publica en el Asset Manager de Unity, en el
        proyecto de Unity que el administrador vinculó a cada uno de tus
        proyectos. Un producto en varios proyectos se crea una sola vez y se
        enlaza a los demas. La publicación es automatica cuando un producto
        termina sin fallos; también se puede forzar desde el detalle del
        producto.
      </p>

      {status.isPending ? (
        <Skeleton className="h-40" />
      ) : status.isError ? (
        <EmptyState title="No se pudo cargar el estado">
          {status.error.message}
        </EmptyState>
      ) : status.data.items.length === 0 ? (
        <EmptyState
          icon={<CloudUpload className="mx-auto size-10" />}
          title="Todavía no se publicó nada en Unity"
        >
          Abrí un producto terminado y usa “Sincronizar con Unity”.
        </EmptyState>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] tracking-wide text-faint uppercase">
                <th className="px-4 py-2.5 font-semibold">Producto</th>
                <th className="px-4 py-2.5 font-semibold">Proyecto</th>
                <th className="px-4 py-2.5 font-semibold">Estado</th>
                <th className="px-4 py-2.5 font-semibold">Asset en Unity</th>
                <th className="px-4 py-2.5 font-semibold">Actualizado</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {status.data.items.map((r) => (
                <tr key={r.id} className="border-t border-line align-top">
                  <td className="px-4 py-2.5 font-medium">{r.product_name}</td>
                  <td className="px-4 py-2.5">
                    {r.project_name}
                    <div className="font-mono text-[11px] text-faint">
                      {r.unity_project_id}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <UnityStatusBadge status={r.status} />
                    {r.attempts > 1 && (
                      <span className="ml-1.5 text-xs text-faint">
                        intento {r.attempts}
                      </span>
                    )}
                    {r.error && (
                      <p className="mt-1 max-w-sm text-xs break-words text-fail">
                        {r.error}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-muted">
                    {r.unity_asset_id ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap text-muted">
                    {fmtDate(r.synced_at ?? r.updated_at)}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {r.status === "FAILED" && s.can("unity:sync") && (
                      <Button
                        size="sm"
                        variant="outline"
                        loading={
                          sync.isPending && sync.variables === r.product_id
                        }
                        onClick={() => sync.mutate(r.product_id)}
                      >
                        Reintentar
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
