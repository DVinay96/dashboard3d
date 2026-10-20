import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { usePlatform, useSavePlatform } from "@/api/queries";
import type { PlatformSettings } from "@/api/types";
import { SuperGate } from "@/components/layout/guards";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/misc";

export const Route = createFileRoute("/admin/platform")({
  component: () => (
    <SuperGate>
      <PlatformPage />
    </SuperGate>
  ),
});

function SettingsForm({ settings }: { settings: PlatformSettings }) {
  const save = useSavePlatform();
  const [blender, setBlender] = useState(settings.blender_path);
  const [unity, setUnity] = useState(settings.unity_export_dir);
  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Entorno</CardTitle>
      </CardHeader>
      <CardBody>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate({ blender_path: blender, unity_export_dir: unity });
          }}
        >
          <Field
            label="Ruta de Blender"
            hint={
              settings.blender_ok
                ? undefined
                : "No se encontró un ejecutable en esa ruta."
            }
          >
            {(id) => (
              <Input
                id={id}
                className="font-mono"
                value={blender}
                onChange={(e) => setBlender(e.target.value)}
                placeholder="/Applications/Blender.app/Contents/MacOS/Blender"
              />
            )}
          </Field>
          <Field
            label="Carpeta local de Unity (opcional)"
            hint="Si la completas, cada modelo que pase el QA en verde se copia ahí. Es independiente del Asset Manager en la nube."
          >
            {(id) => (
              <Input
                id={id}
                className="font-mono"
                value={unity}
                onChange={(e) => setUnity(e.target.value)}
                placeholder="/ruta/a/TuProyecto/Assets/Models"
              />
            )}
          </Field>
          <Button type="submit" loading={save.isPending}>
            Guardar
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function PlatformPage() {
  const platform = usePlatform();
  return (
    <>
      <PageHeader title="Plataforma" />
      {platform.isPending ? (
        <Skeleton className="h-64 max-w-2xl" />
      ) : platform.isError ? (
        <EmptyState title="No se pudieron cargar los ajustes">
          {platform.error.message}
        </EmptyState>
      ) : (
        <SettingsForm settings={platform.data} />
      )}
    </>
  );
}
