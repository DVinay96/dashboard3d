import { createFileRoute } from "@tanstack/react-router";
import { KeyRound, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import {
  useClients,
  useDeleteRole,
  useModules,
  useProjectsOf,
  useRoles,
  useSaveRole,
} from "@/api/queries";
import type { Role, Statement } from "@/api/types";
import { StatementEditor } from "@/components/admin/statement-editor";
import { SuperGate } from "@/components/layout/guards";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { emptyStatement, statementProblems } from "@/lib/iam";

export const Route = createFileRoute("/admin/roles")({
  component: () => (
    <SuperGate>
      <RolesPage />
    </SuperGate>
  ),
});

function RoleForm({ role, onDone }: { role?: Role; onDone: () => void }) {
  const clients = useClients();
  const modules = useModules();
  const save = useSaveRole();
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [scope, setScope] = useState(role?.client_id ?? "");
  const [statements, setStatements] = useState<Statement[]>(
    (role?.statements as Statement[] | undefined) ?? [emptyStatement()],
  );
  const projects = useProjectsOf(scope || null);
  const problem = statementProblems(statements);

  if (modules.isPending) return <Skeleton className="h-40" />;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(
          {
            id: role?.id,
            body: { name, description, statements, client_id: scope || null },
          },
          { onSuccess: onDone },
        );
      }}
    >
      <div className="grid gap-x-4 sm:grid-cols-2">
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
        <Field
          label="Alcance"
          hint={
            role
              ? "El alcance no se puede cambiar."
              : "Un rol del cliente puede referirse a sus proyectos."
          }
        >
          {(id) => (
            <Select
              id={id}
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              disabled={!!role}
            >
              <option value="">Global (cualquier cliente)</option>
              {(clients.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  Solo {c.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <Field label="Descripción">
        {(id) => (
          <Input
            id={id}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        )}
      </Field>
      <h3 className="mb-2 text-xs font-semibold tracking-wider text-muted uppercase">
        Permisos
      </h3>
      <StatementEditor
        initial={statements}
        modules={modules.data ?? []}
        projects={projects.data ?? []}
        onChange={setStatements}
      />
      {problem && <p className="mt-2 text-xs text-warn">{problem}</p>}
      <DialogFooter className="mt-4">
        <Button
          type="submit"
          loading={save.isPending}
          disabled={!name.trim() || !!problem}
        >
          Guardar rol
        </Button>
      </DialogFooter>
    </form>
  );
}

function RoleCard({
  role,
  clientName,
  onEdit,
  onDelete,
}: {
  role: Role;
  clientName?: string;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <Card>
      <CardBody>
        <div className="mb-1 flex items-center gap-2">
          <h2 className="min-w-0 flex-1 truncate font-semibold">{role.name}</h2>
          {role.builtin && <Badge>incluido</Badge>}
          <span className="text-xs text-faint">
            {role.user_count} usuario{role.user_count === 1 ? "" : "s"}
          </span>
        </div>
        <p className="mb-2.5 min-h-5 text-[12.5px] text-muted">
          {role.description}
        </p>
        <pre className="mb-3 max-h-40 overflow-auto rounded-lg border border-line bg-bg p-2.5 font-mono text-[11.5px] break-words whitespace-pre-wrap text-muted">
          {(role.statements as Statement[]).map((st, i) => (
            <span key={i} className="block">
              <b className={st.effect === "allow" ? "text-ok" : "text-fail"}>
                {st.effect.toUpperCase()}
              </b>{" "}
              {st.actions.join(", ")}
              {"\n   "}sobre {st.resources.join(", ")}
            </span>
          ))}
        </pre>
        <div className="flex gap-1.5">
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Pencil className="size-3.5" /> Editar
          </Button>
          {!role.builtin && (
            <Button
              size="sm"
              variant="danger"
              onClick={onDelete}
              aria-label={`Borrar ${role.name}${clientName ? ` de ${clientName}` : ""}`}
            >
              <Trash2 className="size-3.5" />
            </Button>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

function RolesPage() {
  const roles = useRoles();
  const clients = useClients();
  const del = useDeleteRole();
  const confirm = useConfirm();
  const [editing, setEditing] = useState<Role | "new" | null>(null);

  const names = new Map((clients.data ?? []).map((c) => [c.id, c.name]));
  const remove = async (r: Role) => {
    if (
      await confirm({
        title: "Borrar el rol",
        description: `Se borra “${r.name}”.`,
        confirmLabel: "Borrar",
        destructive: true,
      })
    )
      del.mutate(r.id);
  };

  const groups: [string, Role[]][] = [];
  if (roles.data) {
    groups.push([
      "Globales — sirven a cualquier cliente",
      roles.data.filter((r) => !r.client_id),
    ]);
    for (const c of clients.data ?? []) {
      const own = roles.data.filter((r) => r.client_id === c.id);
      if (own.length) groups.push([`Solo ${c.name}`, own]);
    }
  }

  return (
    <>
      <PageHeader
        title="Roles"
        count={roles.data ? `${roles.data.length}` : undefined}
      >
        <Button size="sm" onClick={() => setEditing("new")}>
          <Plus className="size-4" /> Nuevo rol
        </Button>
      </PageHeader>
      <p className="mb-5 max-w-3xl text-[13px] text-muted">
        Un rol es un conjunto de permisos estilo IAM. Lo que permite se limita
        ademas a los módulos que tenga habilitados el cliente del usuario.
        Administrar usuarios, roles y clientes es siempre exclusivo del super
        admin.
      </p>

      {roles.isPending ? (
        <Skeleton className="h-40" />
      ) : roles.isError ? (
        <EmptyState title="No se pudieron cargar los roles">
          {roles.error.message}
        </EmptyState>
      ) : (
        groups.map(([title, list]) => (
          <section key={title} className="mb-7">
            <h2 className="mb-2.5 flex items-center gap-2 text-xs font-semibold tracking-wider text-faint uppercase">
              <KeyRound className="size-3.5" /> {title}
            </h2>
            <div className="grid gap-3.5 md:grid-cols-2 xl:grid-cols-3">
              {list.map((r) => (
                <RoleCard
                  key={r.id}
                  role={r}
                  clientName={r.client_id ? names.get(r.client_id) : undefined}
                  onEdit={() => setEditing(r)}
                  onDelete={() => remove(r)}
                />
              ))}
            </div>
          </section>
        ))
      )}

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        {editing && (
          <DialogContent
            title={editing === "new" ? "Nuevo rol" : `Editar ${editing.name}`}
            className="max-w-3xl"
          >
            <RoleForm
              role={editing === "new" ? undefined : editing}
              onDone={() => setEditing(null)}
            />
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
