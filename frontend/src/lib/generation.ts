export const AI_MODELS = [
  { value: "meshy-7", label: "Calidad alta (v7)" },
  { value: "latest", label: "Última versión" },
  { value: "meshy-6", label: "Estandar (v6)" },
  { value: "meshy-6-lite", label: "Rapida (v6 lite)" },
] as const;

export interface CostInput {
  isLocalModel: boolean;
  textureResolution: string;
  ultra: boolean;
  model: string;
  remesh: boolean;
}

export function estimateCredits(i: CostInput): number {
  if (i.isLocalModel) return 0;
  let c = i.textureResolution === "8k" ? 35 : 30;
  if (i.ultra && ["meshy-7", "latest"].includes(i.model)) c += 5;
  if (i.remesh) c += 5;
  return c;
}

export function defaultPolycount(triBudget: number, topology: string): number {
  return Math.max(
    100,
    Math.round(topology === "quad" ? triBudget / 2 : triBudget),
  );
}

export function expectedTris(polycount: number, topology: string): number {
  return polycount * (topology === "quad" ? 2 : 1);
}

export function exceedsBudget(
  polycount: number,
  topology: string,
  triBudget: number,
): boolean {
  return expectedTris(polycount, topology) > triBudget * 1.05;
}

export const isModelFile = (name: string) => /\.(glb|gltf)$/i.test(name);
export const isPhotoFile = (name: string) => /\.(jpe?g|png)$/i.test(name);
