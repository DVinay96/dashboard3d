import { useEffect, useRef, useState } from "react";
import {
  useBrandFields,
  useCatalog,
  useCreateProduct,
  useProjects,
} from "@/api/queries";
import type { FieldDef } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { CheckRow, Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Dropzone } from "./dropzone";
import {
  MetadataFields,
  defaultsFor,
  type MetaValues,
} from "./metadata-fields";
import { ProjectPicker } from "./project-picker";
import {
  AI_MODELS,
  defaultPolycount,
  estimateCredits,
  exceedsBudget,
  expectedTris,
  isModelFile,
} from "@/lib/generation";
import { fmt } from "@/lib/format";
import { useSession } from "@/lib/session";

interface Options {
  model: string;
  topology: string;
  polycount: number;
  texres: string;
  ultra: boolean;
  remesh: boolean;
  pbr: boolean;
  lightmap: boolean;
  height: string;
  budget: string;
  texturePrompt: string;
}

const INITIAL: Options = {
  model: "meshy-7",
  topology: "quad",
  polycount: 7500,
  texres: "2k",
  ultra: true,
  remesh: true,
  pbr: true,
  lightmap: true,
  height: "0.85",
  budget: "15000",
  texturePrompt: "",
};

function Form({ onDone }: { onDone: () => void }) {
  const s = useSession();
  const canBrands = s.can("brands:read");
  const catalog = useCatalog(canBrands);
  const projects = useProjects();
  const create = useCreateProduct();

  const [name, setName] = useState("");
  const [brandId, setBrandId] = useState("");
  const [meta, setMeta] = useState<MetaValues>({});
  const [files, setFiles] = useState<File[]>([]);
  const [chosenProjects, setChosenProjects] = useState<string[] | null>(null);
  const [o, setO] = useState<Options>(INITIAL);
  const [polyTouched, setPolyTouched] = useState(false);
  const set = <K extends keyof Options>(k: K, v: Options[K]) =>
    setO((prev) => ({ ...prev, [k]: v }));

  const available = (projects.data ?? []).filter((p) => !p.archived);
  const projectIds =
    chosenProjects ??
    (available.length === 1 && available[0] ? [available[0].id] : []);

  const fields = useBrandFields(brandId, canBrands);
  const appliedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!fields.data || appliedFor.current === brandId) return;
    appliedFor.current = brandId;
    setMeta(defaultsFor(fields.data.fields as FieldDef[]));
    const p = fields.data.pipeline as Record<
      string,
      string | number | undefined
    >;
    setO((prev) => ({
      ...prev,
      height:
        p.target_height_m != null ? String(p.target_height_m) : prev.height,
      budget: p.tri_budget != null ? String(p.tri_budget) : prev.budget,
      topology: p.topology ? String(p.topology) : prev.topology,
      texres: p.texture_resolution ? String(p.texture_resolution) : prev.texres,
      texturePrompt: p.texture_prompt
        ? String(p.texture_prompt)
        : prev.texturePrompt,
    }));
    setPolyTouched(false);
  }, [fields.data, brandId]);

  const budget = Number(o.budget) || 0;
  const polycount = polyTouched
    ? o.polycount
    : defaultPolycount(budget, o.topology);
  const isModel = files.length > 0 && isModelFile(files[0]!.name);
  const credits = estimateCredits({
    isLocalModel: isModel,
    textureResolution: o.texres,
    ultra: o.ultra,
    model: o.model,
    remesh: o.remesh,
  });
  const tooMany = exceedsBudget(polycount, o.topology, budget);

  const submit = () => {
    if (!files.length) return;
    const fd = new FormData();
    fd.append("name", name.trim() || files[0]!.name.replace(/\.[^.]+$/, ""));
    fd.append(
      "options",
      JSON.stringify({
        ai_model: o.model,
        ultra_mode: o.ultra,
        should_texture: true,
        enable_pbr: o.pbr,
        texture_resolution: o.texres,
        texture_prompt: o.texturePrompt.trim(),
        should_remesh: o.remesh,
        topology: o.topology,
        target_polycount: polycount,
        target_height_m: Number(o.height) || 0,
        tri_budget: budget,
        lightmap_uv: o.lightmap,
      }),
    );
    fd.append("brand_id", brandId);
    fd.append("metadata", JSON.stringify(meta));
    fd.append("project_ids", JSON.stringify(projectIds));
    files.forEach((f) => fd.append("files", f, f.name));
    create.mutate(fd, { onSuccess: onDone });
  };

  const modeHint = isModel
    ? "Modo modelo local: se saltea la generación, solo acondicionado y QA en Blender. No gasta créditos."
    : files.length === 1
      ? "Con 1 foto se usa image-to-3d (incluye auto_size y origen en la base). Suma mas vistas para reducir la asimetría."
      : "Con 2 a 4 vistas se usa multi-image-to-3d: mejor geometría y menos alucinación. Blender corrige escala y pivote después.";

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <div className="grid gap-x-4 sm:grid-cols-2">
        <Field label="Nombre del producto">
          {(id) => (
            <Input
              id={id}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Silla Cloudrest"
            />
          )}
        </Field>
        <Field label="Marca">
          {(id) => (
            <Select
              id={id}
              value={brandId}
              onChange={(e) => setBrandId(e.target.value)}
              disabled={!canBrands}
            >
              <option value="">Sin marca</option>
              {(catalog.data?.brands ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>

      <Field
        label="Proyectos"
        hint="El producto aparece en cada proyecto que marques."
      >
        {() => (
          <ProjectPicker value={projectIds} onChange={setChosenProjects} />
        )}
      </Field>

      <Field label="Metadatos">
        {() => (
          <MetadataFields
            fields={(fields.data?.fields ?? []) as FieldDef[]}
            values={meta}
            onChange={(k, v) => setMeta((m) => ({ ...m, [k]: v }))}
          />
        )}
      </Field>

      <Field label="Fotos del producto" hint={modeHint}>
        {() => <Dropzone files={files} onChange={setFiles} />}
      </Field>

      <div className="grid gap-x-4 sm:grid-cols-2">
        <Field label="Altura real (m)">
          {(id) => (
            <Input
              id={id}
              type="number"
              step="any"
              min="0"
              value={o.height}
              onChange={(e) => set("height", e.target.value)}
            />
          )}
        </Field>
        <Field label="Budget de tris">
          {(id) => (
            <Input
              id={id}
              type="number"
              step="any"
              min="100"
              value={o.budget}
              onChange={(e) => set("budget", e.target.value)}
            />
          )}
        </Field>
      </div>

      <Field
        label="Prompt de textura (opcional)"
        hint="Con fotos el color sale de la foto y este prompt solo matiza. Para cambiar el material genera primero y usa Cambiar material en el producto terminado."
      >
        {(id) => (
          <Textarea
            id={id}
            value={o.texturePrompt}
            onChange={(e) => set("texturePrompt", e.target.value)}
            placeholder="tapizado de lino gris claro, patas de roble macizo, acabado mate"
          />
        )}
      </Field>

      <details className="mb-4 rounded-lg border border-line">
        <summary className="cursor-pointer px-3.5 py-2.5 font-medium text-muted">
          Parametros de generación
        </summary>
        <div className="border-t border-line p-3.5">
          <div className="grid gap-x-4 sm:grid-cols-2">
            <Field label="Modelo">
              {(id) => (
                <Select
                  id={id}
                  value={o.model}
                  onChange={(e) => set("model", e.target.value)}
                >
                  {AI_MODELS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Topología">
              {(id) => (
                <Select
                  id={id}
                  value={o.topology}
                  onChange={(e) => set("topology", e.target.value)}
                >
                  <option value="quad">quad</option>
                  <option value="triangle">triangle</option>
                </Select>
              )}
            </Field>
            <Field label="Polígonos a pedir">
              {(id) => (
                <Input
                  id={id}
                  type="number"
                  step="any"
                  min="100"
                  max="300000"
                  value={polycount}
                  onChange={(e) => {
                    setPolyTouched(true);
                    set("polycount", Number(e.target.value));
                  }}
                />
              )}
            </Field>
            <Field label="Textura">
              {(id) => (
                <Select
                  id={id}
                  value={o.texres}
                  onChange={(e) => set("texres", e.target.value)}
                >
                  {["2k", "4k", "8k"].map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <p
            className={
              tooMany ? "mb-3 text-xs text-warn" : "mb-3 text-xs text-faint"
            }
          >
            {tooMany
              ? `⚠ El generador va a entregar ~${fmt(expectedTris(polycount, o.topology))} tris y el budget es ${fmt(budget)}: Blender tendra que decimar y re-hornear las texturas.`
              : `El generador entrega ~${fmt(expectedTris(polycount, o.topology))} tris${o.topology === "quad" ? " (1 quad = 2 tris)" : ""}: entra en el budget y las texturas originales quedan intactas.`}
          </p>
          <CheckRow
            checked={o.ultra}
            onChange={(v) => set("ultra", v)}
            label="Ultra mode"
            description="Geometría de mayor fidelidad. +5 créditos, solo en calidad alta y última versión."
          />
          <CheckRow
            checked={o.remesh}
            onChange={(v) => set("remesh", v)}
            label="Remesh"
            description="Sin esto bajas el output crudo: millones de tris, sin UVs."
          />
          <CheckRow
            checked={o.pbr}
            onChange={(v) => set("pbr", v)}
            label="Mapas PBR"
            description="metallic, roughness y normal ademas del base color."
          />
          <CheckRow
            checked={o.lightmap}
            onChange={(v) => set("lightmap", v)}
            label="Canal UV2 de lightmap"
            description="Generado en Blender para el bake de GI en Unity."
          />
          <p className="mt-3 text-[13px] text-muted">
            {isModel ? (
              <>
                Costo: <b className="text-fg">0 créditos</b> (no pasa por el
                generador)
              </>
            ) : (
              <>
                Costo estimado: <b className="text-fg">{credits} créditos</b>
              </>
            )}
          </p>
        </div>
      </details>

      <DialogFooter>
        <Button
          type="submit"
          className="w-full"
          loading={create.isPending}
          disabled={!files.length || !projectIds.length}
        >
          {create.isPending ? "Subiendo…" : "Procesar"}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function NewProductDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open && (
        <DialogContent
          title="Nuevo producto"
          description="Fotos del producto o un modelo .glb existente."
          className="max-w-2xl"
        >
          <Form onDone={() => onOpenChange(false)} />
        </DialogContent>
      )}
    </Dialog>
  );
}
