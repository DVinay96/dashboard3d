import { createFileRoute } from "@tanstack/react-router";
import { Check, Minus } from "lucide-react";
import { useState } from "react";
import { useAccess, useClients, useModules } from "@/api/queries";
import { SuperGate } from "@/components/layout/guards";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";

export const Route = createFileRoute("/admin/access")({
  component: () => (
    <SuperGate>
      <AccessPage />
    </SuperGate>
  ),
});

function AccessPage() {
  const access = useAccess();
  const modules = useModules();
  const clients = useClients();
  const [clientFilter, setClientFilter] = useState("");

  if (access.isPending || modules.isPending)
    return <Skeleton className="h-48" />;
  if (access.isError)
    return (
      <EmptyState title="No se pudo cargar el resumen">
        {access.error.message}
      </EmptyState>
    );

  const rows = access.data.filter(
    (r) => !clientFilter || r.client_id === clientFilter,
  );
  const mods = modules.data ?? [];

  return (
    <>
      <PageHeader
        title="Accesos"
        count={`${rows.length} usuario${rows.length === 1 ? "" : "s"}`}
      >
        <Select
          aria-label="Filtrar por cliente"
          className="w-48"
          value={clientFilter}
          onChange={(e) => setClientFilter(e.target.value)}
        >
          <option value="">Todos los clientes</option>
          {(clients.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </PageHeader>
      <p className="mb-4 max-w-3xl text-[13px] text-muted">
        <Check className="inline size-3.5 text-ok" /> significa que el cliente
        tiene el módulo y algún rol del usuario permite al menos una de sus
        acciones. <Minus className="inline size-3.5" /> significa sin acceso: el
        módulo esta apagado para el cliente o ningún rol del usuario lo cubre.
      </p>
      <Card className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] tracking-wide text-faint uppercase">
              <th className="px-4 py-2.5 font-semibold">Usuario</th>
              <th className="px-4 py-2.5 font-semibold">Cliente</th>
              <th className="px-4 py-2.5 font-semibold">Roles</th>
              {mods.map((m) => (
                <th
                  key={m.id}
                  className="px-3 py-2.5 text-center font-semibold"
                >
                  {m.label}
                </th>
              ))}
              <th className="px-3 py-2.5 text-right font-semibold">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.user_id}
                className={`border-t border-line ${r.disabled ? "opacity-50" : ""}`}
              >
                <td className="px-4 py-2.5">
                  <b className="font-semibold">{r.email}</b>
                  {r.disabled && (
                    <Badge tone="fail" className="ml-1.5">
                      deshabilitado
                    </Badge>
                  )}
                  <div className="text-xs text-faint">{r.display_name}</div>
                </td>
                <td className="px-4 py-2.5 text-muted">
                  {r.client_name ?? "Plataforma"}
                </td>
                <td className="px-4 py-2.5">
                  {r.is_super_admin && <Badge tone="warn">super admin</Badge>}
                  {r.roles.map((n) => (
                    <Badge key={n} className="mr-1">
                      {n}
                    </Badge>
                  ))}
                </td>
                {mods.map((m) => {
                  const on = r.effective_modules.includes(m.id);
                  return (
                    <td key={m.id} className="px-3 py-2.5 text-center">
                      {on ? (
                        <Check
                          className="mx-auto size-4 text-ok"
                          aria-label="Con acceso"
                        />
                      ) : (
                        <Minus
                          className="mx-auto size-4 text-faint"
                          aria-label="Sin acceso"
                        />
                      )}
                    </td>
                  );
                })}
                <td className="px-3 py-2.5 text-right font-mono text-xs text-muted">
                  {r.action_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}
