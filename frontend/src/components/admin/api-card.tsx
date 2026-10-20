import { useState, type ReactNode } from "react";
import { useSaveIntegration, useTestIntegration } from "@/api/queries";
import type { Integration } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { CheckRow, Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/misc";
import { IntegrationStatus } from "./integration-status";
import { SecretInput } from "./secret-input";

export function ApiCard({
  integration: i,
  description,
}: {
  integration: Integration;
  description: ReactNode;
}) {
  const save = useSaveIntegration();
  const test = useTestIntegration();
  const isUnity = i.kind === "unity";
  const [values, setValues] = useState<Record<string, string>>({});
  const [apiBase, setApiBase] = useState(String(i.config.api_base ?? ""));
  const [autoSync, setAutoSync] = useState(i.config.auto_sync !== false);
  const configured = Object.values(i.secrets).every((s) => s.set);
  const set = (k: string, v: string) =>
    setValues((prev) => ({ ...prev, [k]: v }));
  const dirty = Object.values(values).some(Boolean);

  const submit = () =>
    save.mutate(
      {
        id: i.id,
        body: {
          secrets: values,
          ...(isUnity
            ? { config: { api_base: apiBase, auto_sync: autoSync } }
            : {}),
        },
      },
      { onSuccess: () => setValues({}) },
    );

  return (
    <Card>
      <CardBody>
        <div className="mb-1 flex items-center gap-3">
          <h2 className="flex-1 text-[15px] font-semibold">{i.name}</h2>
          <span className="text-xs text-muted">Activa</span>
          <Switch
            label={`${i.name} activa`}
            checked={i.enabled}
            onCheckedChange={(on) =>
              save.mutate({ id: i.id, body: { enabled: on } })
            }
          />
        </div>
        <p className="mb-4 text-[12.5px] text-muted">{description}</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          {i.kind === "meshy" && (
            <SecretInput
              label="API key"
              state={i.secrets.api_key}
              value={values.api_key ?? ""}
              onChange={(v) => set("api_key", v)}
            />
          )}
          {isUnity && (
            <>
              <div className="grid gap-x-4 sm:grid-cols-2">
                <SecretInput
                  label="ID de la cuenta de servicio"
                  state={i.secrets.key_id}
                  value={values.key_id ?? ""}
                  onChange={(v) => set("key_id", v)}
                />
                <SecretInput
                  label="Secreto"
                  state={i.secrets.key_secret}
                  value={values.key_secret ?? ""}
                  onChange={(v) => set("key_secret", v)}
                />
              </div>
              <Field
                label="URL de la API (opcional)"
                hint="Por defecto, https://services.api.unity.com/assets/v1"
              >
                {(id) => (
                  <Input
                    id={id}
                    className="font-mono"
                    value={apiBase}
                    onChange={(e) => setApiBase(e.target.value)}
                  />
                )}
              </Field>
              <CheckRow
                checked={autoSync}
                onChange={setAutoSync}
                label="Sincronizar automaticamente"
                description="Cada producto que termina sin fallos se publica en los proyectos de Unity vinculados, sin tocar nada."
              />
            </>
          )}
          <div className="mt-3 mb-3">
            <IntegrationStatus integration={i} configured={configured} />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="submit"
              loading={save.isPending}
              disabled={
                !dirty &&
                !(
                  isUnity &&
                  (apiBase !== String(i.config.api_base ?? "") ||
                    autoSync !== (i.config.auto_sync !== false))
                )
              }
            >
              Guardar
            </Button>
            <Button
              type="button"
              variant="outline"
              loading={test.isPending && test.variables === i.id}
              disabled={!configured || dirty}
              onClick={() => test.mutate(i.id)}
            >
              Probar conexión
            </Button>
            {configured && (
              <Button
                type="button"
                variant="danger"
                onClick={() =>
                  save.mutate({
                    id: i.id,
                    body: { clear_secrets: Object.keys(i.secrets) },
                  })
                }
              >
                Quitar credenciales
              </Button>
            )}
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
