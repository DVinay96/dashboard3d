import { createFileRoute } from "@tanstack/react-router";
import { Plus, Tags } from "lucide-react";
import { useState } from "react";
import {
  useCatalog,
  useDeleteBrand,
  useSaveBaseFields,
  useSaveBrand,
} from "@/api/queries";
import type { Brand, FieldDef } from "@/api/types";
import { FieldsEditor } from "@/components/brands/fields-editor";
import { TenantGate } from "@/components/layout/guards";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/brands/")({
  component: () => (
    <TenantGate action="brands:read">
      <BrandsPage />
    </TenantGate>
  ),
});

type Selection = "base" | "new" | string;

function BaseEditor({ fields }: { fields: FieldDef[] }) {
  const s = useSession();
  const save = useSaveBaseFields();
  const [draft, setDraft] = useState(fields);
  return (
    <>
      <p className="mb-3 text-[13px] text-muted">
        Campos que llevan todos los productos de tu cliente, sin importar la
        marca. Cada marca puede sumar los suyos.
      </p>
      <FieldsEditor initial={fields} onChange={setDraft} />
      {s.can("brands:update_base") && (
        <Button
          className="mt-4"
          loading={save.isPending}
          onClick={() => save.mutate(draft)}
        >
          Guardar campos base
        </Button>
      )}
    </>
  );
}

function BrandEditor({
  brand,
  onDone,
}: {
  brand?: Brand;
  onDone: (id?: string) => void;
}) {
  const s = useSession();
  const save = useSaveBrand();
  const del = useDeleteBrand();
  const confirm = useConfirm();
  const pl = (brand?.pipeline ?? {}) as Record<
    string,
    string | number | undefined
  >;
  const [name, setName] = useState(brand?.name ?? "");
  const [notes, setNotes] = useState(brand?.notes ?? "");
  const [height, setHeight] = useState(String(pl.target_height_m ?? ""));
  const [budget, setBudget] = useState(String(pl.tri_budget ?? ""));
  const [topology, setTopology] = useState(String(pl.topology ?? ""));
  const [texres, setTexres] = useState(String(pl.texture_resolution ?? ""));
  const [texPrompt, setTexPrompt] = useState(String(pl.texture_prompt ?? ""));
  const [fields, setFields] = useState((brand?.fields ?? []) as FieldDef[]);
  const canWrite = brand ? s.can("brands:update") : s.can("brands:create");

  const submit = () =>
    save.mutate(
      {
        id: brand?.id,
        body: {
          name,
          notes,
          fields,
          pipeline: {
            target_height_m: height,
            tri_budget: budget,
            topology,
            texture_resolution: texres,
            texture_prompt: texPrompt.trim(),
          },
        },
      },
      { onSuccess: (b) => onDone(b.id) },
    );

  const remove = async () => {
    if (!brand) return;
    const ok = await confirm({
      title: "Borrar la marca",
      description: `Se borra “${brand.name}” y los campos que definió.`,
      confirmLabel: "Borrar",
      destructive: true,
    });
    if (ok) del.mutate(brand.id, { onSuccess: () => onDone() });
  };

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
          />
        )}
      </Field>
      <Field label="Notas">
        {(id) => (
          <Textarea
            id={id}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        )}
      </Field>

      <h3 className="mb-2 text-xs font-semibold tracking-wider text-muted uppercase">
        Valores por defecto del pipeline
      </h3>
      <p className="mb-3 text-xs text-faint">
        Se cargan solos al elegir la marca en un producto nuevo.
      </p>
      <div className="grid gap-x-3 sm:grid-cols-4">
        <Field label="Altura real (m)">
          {(id) => (
            <Input
              id={id}
              type="number"
              step="any"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
            />
          )}
        </Field>
        <Field label="Budget de tris">
          {(id) => (
            <Input
              id={id}
              type="number"
              step="any"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          )}
        </Field>
        <Field label="Topología">
          {(id) => (
            <Select
              id={id}
              value={topology}
              onChange={(e) => setTopology(e.target.value)}
            >
              <option value="">—</option>
              <option value="quad">quad</option>
              <option value="triangle">triangle</option>
            </Select>
          )}
        </Field>
        <Field label="Textura">
          {(id) => (
            <Select
              id={id}
              value={texres}
              onChange={(e) => setTexres(e.target.value)}
            >
              <option value="">—</option>
              {["2k", "4k", "8k"].map((r) => (
                <option key={r}>{r}</option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <Field label="Prompt de textura">
        {(id) => (
          <Textarea
            id={id}
            value={texPrompt}
            onChange={(e) => setTexPrompt(e.target.value)}
          />
        )}
      </Field>

      <h3 className="mb-2 text-xs font-semibold tracking-wider text-muted uppercase">
        Campos propios de la marca
      </h3>
      <FieldsEditor
        initial={(brand?.fields ?? []) as FieldDef[]}
        onChange={setFields}
      />

      <div className="mt-5 flex gap-2">
        {canWrite && (
          <Button
            type="submit"
            loading={save.isPending}
            disabled={!name.trim()}
          >
            Guardar marca
          </Button>
        )}
        {brand && s.can("brands:delete") && (
          <Button type="button" variant="danger" onClick={remove}>
            Borrar
          </Button>
        )}
      </div>
    </form>
  );
}

function BrandsPage() {
  const s = useSession();
  const catalog = useCatalog();
  const [sel, setSel] = useState<Selection>("base");

  if (catalog.isPending) return <Skeleton className="h-64" />;
  if (catalog.isError)
    return (
      <EmptyState title="No se pudo cargar el catalogo">
        {catalog.error.message}
      </EmptyState>
    );

  const brands = catalog.data.brands;
  const current = brands.find((b) => b.id === sel);
  const title =
    sel === "base"
      ? "Campos base"
      : sel === "new"
        ? "Nueva marca"
        : (current?.name ?? "Marca");

  const item = (key: string, label: string, sub: string) => (
    <button
      key={key}
      type="button"
      onClick={() => setSel(key)}
      aria-current={sel === key}
      className={cn(
        "w-full cursor-pointer rounded-lg border border-transparent px-3 py-2 text-left hover:bg-panel-2",
        sel === key && "border-line bg-panel-2",
      )}
    >
      <b className="block font-semibold">{label}</b>
      <span className="block text-[11.5px] text-faint">{sub}</span>
    </button>
  );

  return (
    <>
      <PageHeader
        title="Marcas y metadatos"
        count={`${brands.length} marca${brands.length === 1 ? "" : "s"}`}
      >
        {s.can("brands:create") && (
          <Button size="sm" onClick={() => setSel("new")}>
            <Plus className="size-4" /> Nueva marca
          </Button>
        )}
      </PageHeader>
      <div className="grid items-start gap-5 md:grid-cols-[17rem_1fr]">
        <Card>
          <CardBody className="space-y-0.5 p-2.5">
            {item(
              "base",
              "Campos base",
              `${catalog.data.base_fields.length} campos · todas las marcas`,
            )}
            <div className="mt-2 border-t border-line px-3 pt-3 pb-1 text-[10.5px] font-semibold tracking-wider text-faint uppercase">
              Marcas
            </div>
            {brands.length === 0 && (
              <p className="px-3 py-2 text-xs text-faint">
                Todavía no hay marcas.
              </p>
            )}
            {brands.map((b) =>
              item(
                b.id,
                b.name,
                `${b.fields.length} campo${b.fields.length === 1 ? "" : "s"} propios`,
              ),
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <Tags className="size-4 text-faint" />
            <CardTitle>{title}</CardTitle>
          </CardHeader>
          <CardBody>
            {sel === "base" ? (
              <BaseEditor
                key={`base-${catalog.dataUpdatedAt}`}
                fields={catalog.data.base_fields as FieldDef[]}
              />
            ) : sel === "new" ? (
              <BrandEditor key="new" onDone={(id) => setSel(id ?? "base")} />
            ) : current ? (
              <BrandEditor
                key={`${current.id}-${catalog.dataUpdatedAt}`}
                brand={current}
                onDone={(id) => setSel(id ?? "base")}
              />
            ) : (
              <EmptyState title="La marca ya no existe" />
            )}
          </CardBody>
        </Card>
      </div>
    </>
  );
}
