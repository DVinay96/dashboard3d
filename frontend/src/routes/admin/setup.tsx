import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, CheckCircle2, Circle } from "lucide-react";
import { useSetup } from "@/api/queries";
import { SuperGate } from "@/components/layout/guards";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/setup")({
  component: () => (
    <SuperGate>
      <SetupPage />
    </SuperGate>
  ),
});

function SetupPage() {
  const setup = useSetup();
  if (setup.isPending) return <Skeleton className="h-64 max-w-2xl" />;
  if (setup.isError)
    return (
      <EmptyState title="No se pudo cargar la puesta en marcha">
        {setup.error.message}
      </EmptyState>
    );

  const { steps, ready } = setup.data;
  const done = steps.filter((s) => s.done).length;

  return (
    <>
      <PageHeader
        title="Puesta en marcha"
        count={`${done} de ${steps.length}`}
      />
      <p className="mb-5 max-w-2xl text-[13px] text-muted">
        {ready
          ? "Todo lo necesario esta conectado: los clientes ya pueden subir sus objetos y se publican solos en Unity."
          : "Conecta lo que falta y la plataforma queda lista: cada cliente sube sus objetos, los organiza en proyectos y se publican solos en el Asset Manager de Unity."}
      </p>
      <Card className="max-w-2xl divide-y divide-line">
        {steps.map((s) => (
          <div key={s.id} className="flex items-start gap-3 px-4 py-3.5">
            {s.done ? (
              <CheckCircle2
                className="mt-0.5 size-5 shrink-0 text-ok"
                aria-label="Listo"
              />
            ) : (
              <Circle
                className="mt-0.5 size-5 shrink-0 text-faint"
                aria-label="Pendiente"
              />
            )}
            <div className="min-w-0 flex-1">
              <div className={cn("font-semibold", s.done && "text-muted")}>
                {s.title}
              </div>
              <p className="text-[12.5px] break-words text-faint">{s.detail}</p>
            </div>
            {s.link && !s.done && (
              <Link
                to={s.link}
                className={buttonVariants({ size: "sm", variant: "outline" })}
              >
                Resolver <ArrowRight className="size-3.5" />
              </Link>
            )}
          </div>
        ))}
      </Card>
    </>
  );
}
