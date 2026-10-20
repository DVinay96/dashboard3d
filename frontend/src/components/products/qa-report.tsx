import type { Product, QaMetrics, QaSnapshot } from "@/api/types";
import { fmt } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useLightbox } from "./lightbox";

const LEVEL = {
  pass: "text-ok",
  warn: "text-warn",
  fail: "text-fail",
  info: "text-muted",
} as const;

function rows(b: QaSnapshot, a: QaSnapshot): [string, string, string][] {
  const list = (v?: unknown[]) => (v && v.length ? v.join(", ") : "—");
  const out: [string, string, string][] = [
    ["Triangulos", fmt(b.tris), fmt(a.tris)],
    ["Vértices", fmt(b.verts), fmt(a.verts)],
    ["Quads", fmt(b.quads), fmt(a.quads)],
    ["Canales UV", list(b.uv_layers), list(a.uv_layers)],
    [
      "Dimensiones (m)",
      (b.dimensions_m ?? []).join(" × "),
      (a.dimensions_m ?? []).join(" × "),
    ],
    [
      "Base en Z (m)",
      String(b.bbox_min?.[2] ?? "—"),
      String(a.bbox_min?.[2] ?? "—"),
    ],
    [
      "Superficie (m²)",
      String(b.surface_area_m2 ?? "—"),
      String(a.surface_area_m2 ?? "—"),
    ],
    ["Slivers (%)", String(b.sliver_pct ?? "—"), String(a.sliver_pct ?? "—")],
    ["Partes sueltas", fmt(b.loose_parts), fmt(a.loose_parts)],
    ["Aristas de borde", fmt(b.boundary_edges), fmt(a.boundary_edges)],
    [
      "Materiales",
      String(b.materials?.length ?? 0),
      String(a.materials?.length ?? 0),
    ],
  ];
  if (b.uv_stats || a.uv_stats)
    out.push([
      "area UV acumulada (%)",
      String(b.uv_stats?.packing_pct ?? "—"),
      String(a.uv_stats?.packing_pct ?? "—"),
    ]);
  return out;
}

export function QaReport({ product }: { product: Product }) {
  const zoom = useLightbox();
  const m = product.metrics as QaMetrics | null;
  if (!m)
    return (
      <p className="text-[13px] text-faint">Sin resultados de QA todavía.</p>
    );

  const base = `/api/products/${product.id}/files`;
  const shots = [
    ...(m.renders ?? []),
    ...(m.uv_render ? [m.uv_render] : []),
  ].map((f) => ({
    src: `${base}/qa/${f}`,
    caption: f.replace(".png", "").replace("tex_", "textura "),
  }));
  if (product.thumbnail_url)
    shots.unshift({
      src: `${base}/raw/thumbnail.png`,
      caption: "original del generador",
    });

  return (
    <div className="space-y-4">
      {shots.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2.5">
          {shots.map((x) => (
            <figure key={x.src} className="m-0">
              <button
                type="button"
                onClick={() => zoom(x.src, x.caption)}
                className="block w-full cursor-zoom-in overflow-hidden rounded-lg border border-line bg-bg"
              >
                <img
                  src={x.src}
                  alt={x.caption}
                  loading="lazy"
                  className="aspect-square w-full object-contain"
                />
              </button>
              <figcaption className="mt-1 text-center text-[11px] text-faint">
                {x.caption}
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      <div className="space-y-1">
        {(m.checks ?? []).map((c, i) => (
          <div
            key={i}
            className="flex gap-2.5 rounded-md bg-bg px-2.5 py-1.5 text-[12.5px]"
          >
            <b
              className={cn(
                "w-10 shrink-0 text-[11px] uppercase",
                LEVEL[c.level],
              )}
            >
              {c.level}
            </b>
            <span>{c.msg}</span>
          </div>
        ))}
      </div>

      {(m.actions ?? []).length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-[12.5px] text-muted">
          {m.actions!.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}

      {m.before && m.after && (
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="text-left text-[11px] text-faint uppercase">
              <th className="py-1.5 font-semibold">Métrica</th>
              <th className="py-1.5 text-right font-semibold">Origen</th>
              <th className="py-1.5 text-right font-semibold">Acondicionado</th>
            </tr>
          </thead>
          <tbody>
            {rows(m.before, m.after).map(([k, b, a]) => (
              <tr key={k} className="border-t border-line">
                <td className="py-1.5 text-muted">{k}</td>
                <td className="py-1.5 text-right font-mono">{b}</td>
                <td className="py-1.5 text-right font-mono">
                  <span className="mr-1.5 text-faint">→</span>
                  {a}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
