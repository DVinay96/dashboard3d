import { createFileRoute } from "@tanstack/react-router";
import { Plus, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useProducts, useProjects } from "@/api/queries";
import { TenantGate } from "@/components/layout/guards";
import { NewProductDialog } from "@/components/products/new-product-dialog";
import { ProductCard } from "@/components/products/product-card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { useSession } from "@/lib/session";
import { Box } from "lucide-react";

export const Route = createFileRoute("/products/")({
  validateSearch: (s: Record<string, unknown>): { project?: string } => ({
    project: typeof s.project === "string" && s.project ? s.project : undefined,
  }),
  component: () => (
    <TenantGate action="products:list">
      <ProductsPage />
    </TenantGate>
  ),
});

function ProductsPage() {
  const s = useSession();
  const { project } = Route.useSearch();
  const navigate = Route.useNavigate();
  const products = useProducts(project);
  const projects = useProjects();
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title="Productos"
        count={products.data ? `${products.data.length} en total` : undefined}
      >
        {(projects.data?.length ?? 0) > 0 && (
          <Select
            aria-label="Filtrar por proyecto"
            className="w-48"
            value={project ?? ""}
            onChange={(e) =>
              void navigate({
                search: { project: e.target.value || undefined },
              })
            }
          >
            <option value="">Todos los proyectos</option>
            {projects.data!.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => void products.refetch()}
          aria-label="Actualizar"
        >
          <RefreshCw
            className={
              products.isFetching ? "size-3.5 animate-spin" : "size-3.5"
            }
          />
        </Button>
        {s.can("products:create") && (
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="size-4" /> Nuevo producto
          </Button>
        )}
      </PageHeader>

      {products.isPending ? (
        <div className="space-y-3.5">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      ) : products.isError ? (
        <EmptyState title="No se pudieron cargar los productos">
          {products.error.message}
        </EmptyState>
      ) : products.data.length === 0 ? (
        <EmptyState
          icon={<Box className="mx-auto size-10" />}
          title="Todavía no hay productos"
        >
          {s.can("products:create")
            ? "Subí fotos o un .glb para empezar."
            : "Cuando se cree alguno, lo vas a ver aca."}
        </EmptyState>
      ) : (
        products.data.map((p) => <ProductCard key={p.id} product={p} />)
      )}

      <NewProductDialog open={creating} onOpenChange={setCreating} />
    </>
  );
}
