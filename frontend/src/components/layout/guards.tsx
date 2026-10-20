import { Link } from "@tanstack/react-router";
import { Lock, Building2 } from "lucide-react";
import type { ReactNode } from "react";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/misc";
import { useSession } from "@/lib/session";

export function TenantGate({
  action,
  children,
}: {
  action?: string;
  children: ReactNode;
}) {
  const s = useSession();
  if (!s.me.client)
    return (
      <EmptyState
        icon={<Building2 className="mx-auto size-10" />}
        title="Elegí un cliente para operar"
      >
        Estas en modo plataforma. Elegí un cliente arriba, o crea el primero
        desde{" "}
        <Link
          to="/admin/clients"
          className={buttonVariants({ variant: "ghost", size: "sm" })}
        >
          Clientes
        </Link>
        .
      </EmptyState>
    );
  if (action && !s.can(action)) return <NoAccess />;
  return <>{children}</>;
}

export function SuperGate({ children }: { children: ReactNode }) {
  const s = useSession();
  return s.isSuper ? <>{children}</> : <NoAccess />;
}

export function NoAccess() {
  return (
    <EmptyState
      icon={<Lock className="mx-auto size-10" />}
      title="No tenés acceso a esta sección"
    >
      Tu rol, o los módulos de tu cliente, no la incluyen. Pedile acceso al
      administrador.
    </EmptyState>
  );
}
