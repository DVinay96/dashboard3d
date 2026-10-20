import { createFileRoute } from "@tanstack/react-router";
import { Pencil, Plus, Trash2, Users } from "lucide-react";
import { useState } from "react";
import {
  useClients,
  useCreateUser,
  useDeleteUser,
  useRoles,
  useUpdateUser,
  useUsers,
} from "@/api/queries";
import type { User } from "@/api/types";
import { SuperGate } from "@/components/layout/guards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { CheckRow, Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { useSession } from "@/lib/session";

export const Route = createFileRoute("/admin/users")({
  component: () => (
    <SuperGate>
      <UsersPage />
    </SuperGate>
  ),
});

function UserForm({
  user,
  defaultClient,
  onDone,
}: {
  user?: User;
  defaultClient: string;
  onDone: () => void;
}) {
  const clients = useClients();
  const create = useCreateUser();
  const update = useUpdateUser();
  const [email, setEmail] = useState(user?.email ?? "");
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [isSuper, setIsSuper] = useState(false);
  const [clientId, setClientId] = useState(user?.client_id ?? defaultClient);
  const [roleIds, setRoleIds] = useState(user?.role_ids ?? []);
  const [disabled, setDisabled] = useState(user?.disabled ?? false);
  const roles = useRoles(clientId || undefined);
  const editingSuper = user?.is_super_admin ?? false;

  const submit = () =>
    user
      ? update.mutate(
          {
            id: user.id,
            body: { display_name: displayName, role_ids: roleIds, disabled },
          },
          { onSuccess: onDone },
        )
      : create.mutate(
          {
            email,
            display_name: displayName,
            client_id: isSuper ? null : clientId,
            role_ids: roleIds,
            is_super_admin: isSuper,
          },
          { onSuccess: onDone },
        );

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="grid gap-x-4 sm:grid-cols-2">
        <Field
          label="Email"
          hint={
            user ? undefined : "Con OIDC, el usuario entrara con este email."
          }
        >
          {(id) => (
            <Input
              id={id}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={!!user}
              required
              autoFocus={!user}
            />
          )}
        </Field>
        <Field label="Nombre visible">
          {(id) => (
            <Input
              id={id}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              autoFocus={!!user}
            />
          )}
        </Field>
      </div>
      {!user && (
        <CheckRow
          checked={isSuper}
          onChange={setIsSuper}
          label="Super admin"
          description="Administra la plataforma entera: clientes, usuarios y roles. No pertenece a ningún cliente."
        />
      )}
      {!isSuper && !editingSuper && (
        <>
          <Field label="Cliente" className="mt-3">
            {(id) => (
              <Select
                id={id}
                value={clientId}
                onChange={(e) => {
                  setClientId(e.target.value);
                  setRoleIds([]);
                }}
                disabled={!!user}
                required
              >
                <option value="" disabled>
                  Elegí un cliente…
                </option>
                {(clients.data ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field
            label="Roles"
            hint="Los permisos de cada rol se limitan a los módulos que tenga el cliente."
          >
            {() => (
              <div className="rounded-lg border border-line p-2.5">
                {!clientId && (
                  <p className="text-xs text-faint">
                    Elegí primero el cliente.
                  </p>
                )}
                {(roles.data ?? []).map((r) => (
                  <CheckRow
                    key={r.id}
                    checked={roleIds.includes(r.id)}
                    onChange={(on) =>
                      setRoleIds(
                        on
                          ? [...roleIds, r.id]
                          : roleIds.filter((x) => x !== r.id),
                      )
                    }
                    label={
                      <>
                        {r.name}{" "}
                        {r.client_id && (
                          <Badge tone="accent">del cliente</Badge>
                        )}
                      </>
                    }
                    description={r.description}
                  />
                ))}
              </div>
            )}
          </Field>
        </>
      )}
      {user && (
        <CheckRow
          checked={disabled}
          onChange={setDisabled}
          label="Deshabilitado"
          description="No puede operar mientras esté marcado."
        />
      )}
      <DialogFooter>
        <Button
          type="submit"
          loading={create.isPending || update.isPending}
          disabled={!user && !isSuper && !clientId}
        >
          Guardar
        </Button>
      </DialogFooter>
    </form>
  );
}

function UsersPage() {
  const s = useSession();
  const [clientFilter, setClientFilter] = useState("");
  const users = useUsers(clientFilter || undefined);
  const clients = useClients();
  const del = useDeleteUser();
  const confirm = useConfirm();
  const [editing, setEditing] = useState<User | "new" | null>(null);

  const remove = async (u: User) => {
    if (
      await confirm({
        title: "Borrar el usuario",
        description: `Se borra ${u.email}.`,
        confirmLabel: "Borrar",
        destructive: true,
      })
    )
      del.mutate(u.id);
  };

  return (
    <>
      <PageHeader
        title="Usuarios"
        count={users.data ? `${users.data.length}` : undefined}
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
        <Button size="sm" onClick={() => setEditing("new")}>
          <Plus className="size-4" /> Nuevo usuario
        </Button>
      </PageHeader>

      {users.isPending ? (
        <Skeleton className="h-40" />
      ) : users.isError ? (
        <EmptyState title="No se pudieron cargar los usuarios">
          {users.error.message}
        </EmptyState>
      ) : users.data.length === 0 ? (
        <EmptyState
          icon={<Users className="mx-auto size-10" />}
          title="No hay usuarios"
        />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] tracking-wide text-faint uppercase">
                <th className="px-4 py-2.5 font-semibold">Usuario</th>
                <th className="px-4 py-2.5 font-semibold">Cliente</th>
                <th className="px-4 py-2.5 font-semibold">Roles</th>
                <th className="px-4 py-2.5 font-semibold">Estado</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => (
                <tr
                  key={u.id}
                  className={`border-t border-line ${u.disabled ? "opacity-55" : ""}`}
                >
                  <td className="px-4 py-2.5">
                    <b className="font-semibold">{u.email}</b>
                    {u.id === s.me.user.id && (
                      <Badge className="ml-1.5">vos</Badge>
                    )}
                    <div className="text-xs text-faint">{u.display_name}</div>
                  </td>
                  <td className="px-4 py-2.5 text-muted">
                    {u.client_name ?? "Plataforma"}
                  </td>
                  <td className="px-4 py-2.5">
                    {u.is_super_admin && <Badge tone="warn">super admin</Badge>}
                    {u.role_names.map((n) => (
                      <Badge key={n} className="mr-1">
                        {n}
                      </Badge>
                    ))}
                    {!u.is_super_admin && u.role_names.length === 0 && (
                      <span className="text-faint">sin roles</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {u.disabled ? (
                      <Badge tone="fail">deshabilitado</Badge>
                    ) : (
                      <span className="text-muted">Activo</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right whitespace-nowrap">
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Editar ${u.email}`}
                      onClick={() => setEditing(u)}
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                    {u.id !== s.me.user.id && (
                      <Button
                        size="icon"
                        variant="danger"
                        aria-label={`Borrar ${u.email}`}
                        onClick={() => remove(u)}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        {editing && (
          <DialogContent
            title={
              editing === "new" ? "Nuevo usuario" : `Editar ${editing.email}`
            }
          >
            <UserForm
              user={editing === "new" ? undefined : editing}
              defaultClient={clientFilter}
              onDone={() => setEditing(null)}
            />
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
