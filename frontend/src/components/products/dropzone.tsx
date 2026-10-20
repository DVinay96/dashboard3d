import { ImagePlus, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { isModelFile, isPhotoFile } from "@/lib/generation";
import { cn } from "@/lib/utils";

export const MAX_PHOTOS = 4;

export function mergeFiles(current: File[], incoming: File[]): File[] {
  const valid = incoming.filter(
    (f) => isModelFile(f.name) || isPhotoFile(f.name),
  );
  const model = valid.find((f) => isModelFile(f.name));
  if (model) return [model];
  const photos = valid.filter((f) => isPhotoFile(f.name));
  const base = current.some((f) => isModelFile(f.name)) ? [] : current;
  return [...base, ...photos].slice(0, MAX_PHOTOS);
}

export function Dropzone({
  files,
  onChange,
}: {
  files: File[];
  onChange: (files: File[]) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const previews = useMemo(
    () =>
      files.map((f) => (isPhotoFile(f.name) ? URL.createObjectURL(f) : null)),
    [files],
  );
  useEffect(
    () => () => previews.forEach((u) => u && URL.revokeObjectURL(u)),
    [previews],
  );

  const add = (list: FileList | null) =>
    list && onChange(mergeFiles(files, [...list]));

  return (
    <div>
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          add(e.dataTransfer.files);
        }}
        className={cn(
          "w-full cursor-pointer rounded-[9px] border-[1.5px] border-dashed border-line bg-bg px-4 py-6 text-center transition-colors hover:border-accent hover:bg-accent/5",
          over && "border-accent bg-accent/5",
        )}
      >
        <ImagePlus className="mx-auto mb-1.5 size-6 text-faint" />
        <p className="text-[13px] text-muted">
          <b className="text-fg">Arrastra 1 a 4 fotos</b> o hacé clic
        </p>
        <small className="text-xs text-faint">
          La 1ª es la vista frontal · también acepta un .glb existente
        </small>
      </button>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        accept=".jpg,.jpeg,.png,.glb,.gltf"
        onChange={(e) => {
          add(e.target.files);
          e.target.value = "";
        }}
      />
      {files.length > 0 && (
        <ul className="mt-2.5 flex flex-wrap gap-2">
          {files.map((f, i) => (
            <li
              key={f.name + i}
              className="relative size-[72px] overflow-hidden rounded-lg border border-line bg-bg"
            >
              {previews[i] ? (
                <img
                  src={previews[i]}
                  alt={f.name}
                  className="size-full object-cover"
                />
              ) : (
                <span className="grid size-full place-items-center px-1 text-center text-[10px] break-all text-muted">
                  {f.name}
                </span>
              )}
              {previews[i] && (
                <span className="absolute bottom-0 left-0 rounded-tr bg-black/70 px-1 text-[10px] text-white">
                  {i === 0 ? "frente" : `v${i + 1}`}
                </span>
              )}
              <button
                type="button"
                aria-label={`Quitar ${f.name}`}
                onClick={() => onChange(files.filter((_, j) => j !== i))}
                className="absolute top-0.5 right-0.5 grid size-5 cursor-pointer place-items-center rounded-full bg-black/70 text-white hover:bg-fail"
              >
                <X className="size-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
