import { useProjects } from "@/api/queries";
import { Badge } from "@/components/ui/badge";
import { CheckRow } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/misc";

export function ProjectPicker({
  value,
  onChange,
}: {
  value: string[];
  onChange: (ids: string[]) => void;
}) {
  const projects = useProjects();
  if (projects.isPending) return <Skeleton className="h-16" />;
  const active = (projects.data ?? []).filter((p) => !p.archived);
  if (!active.length)
    return (
      <p className="text-xs text-faint">
        No hay proyectos disponibles para vos. Crea uno en Proyectos.
      </p>
    );
  const toggle = (id: string, on: boolean) =>
    onChange(on ? [...value, id] : value.filter((x) => x !== id));
  return (
    <div
      className="rounded-lg border border-line p-2.5"
      role="group"
      aria-label="Proyectos"
    >
      {active.map((p) => (
        <CheckRow
          key={p.id}
          checked={value.includes(p.id)}
          onChange={(on) => toggle(p.id, on)}
          label={
            <>
              {p.name}{" "}
              {p.unity_project_id && <Badge tone="accent">Unity</Badge>}
            </>
          }
          description={p.description || undefined}
        />
      ))}
    </div>
  );
}
