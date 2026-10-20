# Pipeline 3D

Pipeline local: **fotos de producto → modelo 3D listo para Unity**, con control de calidad automatico.

Resuelve el problema concreto de bajar el output crudo del generador (millones de triangulos,
sin UVs, sin escala real) en lugar de un asset de producción.

```
fotos ──► generador 3D ──► Blender headless ──► QA ──► GLB + FBX
          (flags        (escala real,        (11 checks     (+ copia opcional
           correctos)    pivote, UVs,         + renders)      a Unity)
                         budget de tris)
```

---

## Requisitos

- **Python 3.10+** (probado en 3.13) y **Node 20+** (solo para compilar el frontend)
- **Blender 4.x o 5.x** — se detecta solo en las rutas habituales
- **API key del generador 3D** — solo si vas a generar desde fotos
- **Cuenta de servicio de Unity** — solo si vas a publicar en el Asset Manager

## Arranque

```bash
./run.sh
```

Abrí <http://127.0.0.1:8765>: la pantalla **Puesta en marcha** te guía por lo que falta conectar (Blender, Meshy, Unity, primer cliente, proyectos vinculados). La primera vez `run.sh` crea el entorno de Python y
compila el frontend; después arranca directo. El servidor escucha **únicamente en
127.0.0.1**.

Para desarrollar: `./dev.sh` levanta la API con recarga y Vite (con HMR) en
<http://localhost:5173>. Tests: `cd backend && ../.venv/bin/python -m pytest` y
`cd frontend && npm test`.

> **Sin autenticación (por ahora).** Hasta integrar OIDC, `AUTH_MODE=none`: cualquiera
> que llegue al servidor actúa como super admin. Por eso escucha solo en `127.0.0.1`;
> no lo expongas en una red. Para probar clientes y roles, el selector **Ver como…**
> de la barra superior te deja actuar como cualquier usuario.

### Conectar APIs, MCP y agentes

Todo lo externo se conecta desde la interfaz, en **Integraciones** (solo super admin); no hace
falta tocar archivos:

| Integración              | Qué se carga                          | Para qué                                                    |
| ------------------------ | ------------------------------------- | ----------------------------------------------------------- |
| **Generador 3D (Meshy)** | API key                               | crear modelos desde fotos                                   |
| **Unity Asset Manager**  | ID y secreto de la cuenta de servicio | publicar en Unity (con opción de sincronización automatica) |
| **Servidor MCP**         | URL, token (Bearer) y herramienta     | que un agente reciba los eventos de la plataforma           |
| **Webhook**              | URL y secreto de firma                | que cualquier sistema reciba los eventos                    |

Las credenciales se guardan **cifradas** (Fernet) y **nunca se vuelven a mostrar**: la interfaz solo
indica que estan guardadas. Cada integración tiene **Probar conexión**: Meshy consulta el saldo,
Unity lista las bibliotecas, un MCP hace `initialize` y `tools/list`, y un webhook recibe un `ping`.

La clave de cifrado se genera sola en `data/secrets.key` (permisos 600); para fijarla desde el
entorno, definí `SECRETS_KEY` (una clave Fernet). **Hacé copia de esa clave junto con la base**: sin ella
las credenciales guardadas no se pueden descifrar. Como alternativa, `MESHY_API_KEY`, `UNITY_KEY_ID` y
`UNITY_KEY_SECRET` en el entorno siguen funcionando si la interfaz no tiene nada cargado.

---

## Dos modos de uso

### 1. Desde fotos (consume créditos)

Arrastra **1 a 4 fotos** del producto. La primera es la vista frontal.

| Fotos | Endpoint             | Qué aporta                                                                         |
| ----- | -------------------- | ---------------------------------------------------------------------------------- |
| 1     | `/image-to-3d`       | Incluye `auto_size` + `origin_at:bottom`: escala real y pivote resueltos en origen |
| 2–4   | `/multi-image-to-3d` | **Mucha menos asimetría**: el modelo deja de inventar las caras que no ve          |

Con 2–4 vistas la escala y el pivote los corrige Blender después, porque esos dos
parametros no existen en el endpoint multi-imagen.

**Recomendación:** 3 fotos (frente, lado, atras). La asimetría es el defecto que
ningún post-proceso arregla, y las vistas extra son la única palanca real contra ella.

### 2. Desde un modelo existente (gratis)

Arrastra un `.glb` y se saltea la generación: solo corre acondicionado + QA. Sirve para
probar el pipeline sin gastar créditos y para pasar assets del equipo 3D o de
catalogo por el mismo control de calidad.

---

## Qué hace el paso de Blender

1. Aplica las transformaciones heredadas del import
2. Escala a la **altura real en metros** que indicaste
3. Mueve el **pivote a base-centro** (el modelo queda parado en el piso, en el origen)
4. Decima al **budget de triangulos**
5. Genera **UVs** si faltan (Smart Project)
6. Genera el **canal UV2 de lightmap** para el bake de GI en Unity
7. Shade smooth por angulo (40°)
8. Exporta **GLB** + **FBX** con los ejes de Unity (`-Z` forward, `Y` up, escala 1.0)

> **Detalle no obvio:** si el modelo ya traía UVs y se decima fuerte, el collapse
> las deja con islas superpuestas y caras invertidas. El script las descarta y
> rehace el unwrap. Sin esto, el asset sale con la textura repetida — lo verificamos
> midiendo 138% de area UV acumulada antes del fix.

> **Modelos con textura:** si hay que decimar, rehacer las UVs y reusar la imagen
> original produce un mosaico (cada cara lee una zona equivocada de la textura).
> En ese caso el script guarda una copia del original y **hornea high→low**
> base color, roughness, metallic y normal sobre las UVs nuevas (~10 s a 2048 px).
> Mejor todavía: pedir un polycount que ya entre en el budget
> (el dashboard lo sincroniza solo: con topología quad, la mitad del budget),
> así no se decima y las texturas originales quedan intactas.

## Cambiar el material (re-texturizar)

Con fotos, **el color sale de la foto**: en `/image-to-3d` el `texture_prompt` solo
matiza. Una silla blanca en la foto sale blanca aunque pidas "piel negra" (lo
verificamos: el generador recibió el prompt y su propia miniatura salió blanca igual).

Para cambiar el material, abrí un producto terminado → **Cambiar material** →
describí el material. Usa `/retexture` con el `input_task_id` del producto: la
geometría no cambia, solo se re-pinta la textura, y el texto es la instrucción
principal. Se crea un producto nuevo (el original no se toca) y pasa por el mismo
acondicionado + QA. Consume créditos del generador; el consumo real se ve en la tarjeta.

La miniatura **original del generador** aparece primera entre los renders: sirve para
distinguir "salió así de origen" de "lo rompió el pipeline".

## Marcas y metadatos

Cada producto pertenece a una marca y lleva metadatos. Las marcas, sus campos y los
campos base son **de cada cliente** (un cliente no ve los de otro). El esquema tiene
dos niveles:

- **Campos base** — iguales para todas las marcas del cliente. Vienen con SKU, nombre
  comercial y precio; se editan en **Marcas → Campos base**.
- **Campos propios de la marca** — se suman a los base. No pueden repetir sus claves.

Tipos disponibles: texto, número, lista (opciones separadas por coma), sí/no y fecha.
Cada campo puede ser obligatorio y tener un valor por defecto.

Una marca también guarda **valores por defecto del pipeline** (altura real, budget de
tris, topología, resolución y prompt de textura). Al elegirla en el formulario, esos
valores se cargan solos junto con sus campos ya completados con los defaults.

Las claves se derivan del nombre visible con los acentos transliterados:
"Colección" → `coleccion`.

Al terminar el QA se escribe un **sidecar** `out/<slug>.metadata.json` junto al GLB y
el FBX, con la marca, todos los campos y qué modelos se exportaron. Viaja con los
modelos a Unity.

Una marca en uso no se puede borrar: el servidor responde qué productos la usan.

## Los checks de QA

| Check        | Falla cuando                                            |
| ------------ | ------------------------------------------------------- |
| `polycount`  | 50% por encima del budget                               |
| `uv`         | no hay UVs                                              |
| `uv2`        | falta el canal de lightmap _(aviso)_                    |
| `uv_overlap` | area UV acumulada > 101% → islas superpuestas           |
| `uv_packing` | aprovechamiento < 25% _(aviso)_                         |
| `uv_flipped` | caras con UV invertida                                  |
| `scale`      | altura fuera del ±2% del objetivo                       |
| `pivot`      | la base no esta en Z=0                                  |
| `pivot_xy`   | descentrado en XY _(aviso)_                             |
| `symmetry`   | error de espejado > 2% promedio u 8% pico               |
| `slivers`    | > 40% de triangulos degenerados _(aviso)_               |
| `textures`   | UVs regeneradas en un modelo texturizado sin re-hornear |

Si el modelo tiene textura, ademas de los renders en gris se generan `tex_q34` y
`tex_front` con los materiales reales: el render gris no muestra errores de textura.

### Sobre el check de simetría

Es el que detecta la geometría alucinada. No mide el bounding box (centrar el pivote
lo vuelve simétrico por construcción y el check quedaría siempre en verde): espeja
cada vértice contra el plano YZ y mide la distancia al vecino mas cercano con un KD-tree.

Se mide sobre el **modelo original**, no sobre el decimado, porque el collapse colapsa
vértices distinto en cada lado e introduce falsos positivos.

El promedio se diluye porque la mayor parte de un objeto suele ser simétrica, así que
**el pico es la señal real**. Medido sobre los dos modelos de referencia:

|                       | promedio | pico     | veredicto                    |
| --------------------- | -------- | -------- | ---------------------------- |
| Modelo crudo generado | 0.45%    | **5.8%** | aviso — asimetría localizada |
| Asset del equipo 3D   | 0.36%    | 2.8%     | ok                           |

---

## Resultados medidos

Corriendo el modo modelo local sobre los dos archivos de referencia:

|            | Modelo crudo | → acondicionado      | Asset 3D | → acondicionado  |
| ---------- | ------------ | -------------------- | -------- | ---------------- |
| Triangulos | 3,122,006    | **15,000**           | 164,774  | **14,999**       |
| Peso       | 53.6 MB      | **1.9 MB**           | 4.8 MB   | 1.9 MB           |
| Canales UV | ninguno      | **UVMap + Lightmap** | UVMap    | UVMap + Lightmap |
| Altura     | 1.90 u       | **0.850 m**          | 0.828 m  | 0.850 m          |
| Base en Z  | −0.952       | **−0.0002**          | −0.003   | −0.0002          |
| Superficie | 8.68 m²      | 1.73 m²              | 1.71 m²  | 1.73 m²          |

La superficie convergente (1.73 vs 1.71 m²) confirma que la escala quedó bien.

---

## Clientes, módulos y permisos

La plataforma es **multi-cliente**. El **super admin** (único rol de plataforma) crea
clientes y decide **a qué módulos accede cada uno**; cada cliente tiene sus propios
usuarios, proyectos, marcas y productos, invisibles para los demas.

| Módulo                       | Qué habilita                                                              |
| ---------------------------- | ------------------------------------------------------------------------- |
| **Catalogo y proyectos**     | ver productos, descargarlos, organizarlos en proyectos                    |
| **Generación 3D**            | crear desde fotos o un GLB, cambiar material, reprocesar (gasta créditos) |
| **Marcas y metadatos**       | definir marcas y el esquema de metadatos                                  |
| **Sincronización con Unity** | publicar en el Asset Manager de Unity                                     |

Los módulos se activan y apagan en **Clientes** y rigen de inmediato. **Accesos** muestra,
para cada usuario, a qué módulos accede _de verdad_ (módulos del cliente ∩ lo que
permiten sus roles).

### Roles (estilo AWS IAM)

Un rol es una lista de _statements_ `allow`/`deny` sobre **acciones** y **recursos**:

```json
{
  "effect": "allow",
  "actions": ["products:*", "unity:sync"],
  "resources": ["project/<id>", "project/<id>/*"]
}
```

1. Un `deny` explícito siempre gana; lo que no esta permitido queda prohibido.
2. Un usuario con varios roles suma sus permisos.
3. Una acción solo vale si el **módulo** que la contiene esta habilitado para el cliente.
4. Los permisos se leen en cada request: editar un rol surte efecto sin que nadie reingrese.
5. Un producto en varios proyectos es visible por cualquiera de ellos, y un `deny` en uno cualquiera gana.

Recursos: `project/<id>` (un proyecto), `project/<id>/product/*` (sus productos),
`brand/<id>` o `brand/none` (marcas), `schema/base` (campos base). Los roles pueden ser
**globales** (sirven a cualquier cliente) o **de un cliente** (pueden nombrar sus proyectos).
Vienen cuatro globales: Solo lectura, Operador, Gestor y Administrador del cliente.

Administrar clientes, usuarios, roles y la plataforma es **siempre del super admin**:
ningún rol puede otorgarlo, así nadie escala privilegios editando un rol. El sistema impide
borrar o deshabilitar al último super admin, y que alguien lo haga con su propia cuenta.

### Sin autenticación hoy, OIDC mañana

`app/identity.py` es el único lugar que decide _quién_ hace cada petición. Con
`AUTH_MODE=none` devuelve al super admin local (o al usuario de **Ver como…**). Integrar
OIDC es implementar ahí la validación del token y buscar al usuario por email/`sub`; los
usuarios ya se identifican por email, sin contraseñas. `GET /api/dev/identities` y las
cabeceras `X-Act-As` / `X-Client-Id` son solo para este modo y desaparecen con OIDC.

## Publicar en Unity (Asset Manager)

Una **sola cuenta de servicio** de la plataforma publica en **nuestra** organización de Unity. Cada
proyecto de un cliente se vincula (lo hace el super admin, en **Proyectos → Editar** con el cliente
elegido) con un proyecto de Unity.

**La publicación es automatica.** Cuando un producto termina sin fallos de QA, si el cliente tiene el
módulo Unity y alguno de sus proyectos tiene destino, se publica solo (se puede apagar en
Integraciones → Unity). Al asignar un producto terminado a otro proyecto, se enlaza al instante.
También se puede forzar desde el detalle del producto con **Sincronizar con Unity**.

Qué hace, por producto:

1. crea el asset (`3D Model`) con su nombre, cliente, marca, SKU y quién lo creó;
2. sube el GLB, el FBX y el `.metadata.json` (URL firmada + _finalize_);
3. envía la versión (_autosubmit_) y la **enlaza** a los demas proyectos: un producto en varios
   proyectos se crea **una sola vez**.

Cada paso se guarda: si algo falla, **Reintentar** retoma sin recrear el asset ni volver a subir lo
ya subido. El estado por proyecto esta en **Unity**. La cuenta de servicio necesita el rol _Asset
Manager Contributor_ (o Admin) en esos proyectos. Las rutas siguen la
[referencia oficial](https://docs.unity.com/en-us/oas-assets-client/1.0.0); los tests usan un Unity
simulado, así que el primer uso real conviene probarlo con un producto de prueba.

## Eventos para agentes, MCP y webhooks

La plataforma avisa de lo que pasa para que tus agentes reaccionen:

| Evento              | Cuando                               |
| ------------------- | ------------------------------------ |
| `product.done`      | un producto terminó sin fallos de QA |
| `product.qa_failed` | terminó con fallos de QA             |
| `product.failed`    | el procesamiento falló               |
| `unity.synced`      | se publicó en Unity                  |
| `unity.failed`      | falló la publicación en Unity        |

Cada conector elige a qué eventos se suscribe. El cuerpo es JSON:

```json
{
  "event": "product.done",
  "occurred_at": 1790000000.0,
  "client": { "id": "…", "name": "Acme", "slug": "acme" },
  "product": {
    "id": "…",
    "name": "Silla",
    "status": "DONE",
    "brand": "Nórdica",
    "metadata": { "sku": "S-1" },
    "projects": [{ "id": "…", "name": "General", "unity_project_id": "…" }],
    "created_by": "ana@acme.com",
    "error": null
  },
  "unity": [
    { "project": "General", "status": "SYNCED", "asset_id": "…", "error": null }
  ]
}
```

- **Webhook:** `POST` con `X-Pipeline-Event` y, si configuraste secreto, `X-Pipeline-Signature:
sha256=<HMAC-SHA256 del cuerpo crudo>`. Se reintenta con espera ante errores 5xx/429 (3 intentos);
  el resultado queda en la tarjeta del conector.
- **MCP:** si indicas una herramienta, se la invoca por `tools/call` con `{ "event": …, "payload": … }`
  (Streamable HTTP, con sesión y token Bearer).

---

## Estructura

```
backend/
  app/
    main.py             aplicación FastAPI (API en /api + frontend compilado)
    models.py           modelo: clientes, proyectos, marcas, usuarios, roles, productos
    modules.py          módulos y las acciones que habilita cada uno
    policy.py           evaluación de permisos estilo IAM
    identity.py         quién hace la petición (hoy sin autenticación; aquí va OIDC)
    routers/            endpoints por recurso
    services/           pipeline (Meshy + Blender), cola de trabajos, Unity, integraciones,
                        cifrado de credenciales, eventos (webhook/MCP), importación
    qa_blender.py       acondicionado + métricas + renders (corre dentro de Blender)
  alembic/              migraciones del esquema
  tests/                pytest (API real contra una base temporal)
frontend/               React + TypeScript + Vite (Tailwind, TanStack Query/Router)
  src/api/              cliente tipado, generado desde el OpenAPI del backend
data/                   (no se versiona)
  pipeline.db           base de datos SQLite
  products/<id>/        input/ raw/ out/ (GLB+FBX → Unity) qa/ log.txt
```

La API se documenta sola en <http://127.0.0.1:8765/docs>. Si cambias un endpoint,
`cd frontend && npm run gen:api` regenera los tipos del frontend.

**Datos de la versión anterior.** Si hay un `data/brands.json` o `data/products/*/meta.json`
de la versión sin base de datos, el primer arranque los importa solos a un cliente
«Cliente por defecto» (con todos los módulos y un proyecto «General»). No borra nada.

**Postgres.** SQLite alcanza para un servidor; para mas, apunta `DATABASE_URL` a Postgres
(instalando el driver) y las migraciones de Alembic crean el esquema.

## Import en Unity

Los FBX salen con los ejes correctos, así que en el importer:

- **Scale Factor** 1, **Convert Units** off
- **Generate Lightmap UVs** off (ya viene el canal UV2)
- **Read/Write** off salvo que necesites modificar la malla en runtime
- **Mesh Compression** medium para props de fondo

Si completas la carpeta local de Unity en **Plataforma**, cada modelo que pase el QA en
verde se copia ahí automaticamente (independiente de la publicación en el Asset Manager).

---

## Costos de generación

| Concepto                                            | Créditos |
| --------------------------------------------------- | -------- |
| Base con textura 2k/4k                              | 30       |
| Textura 8k                                          | 35       |
| Ultra mode (calidad alta)                           | +5       |
| Remesh                                              | +5       |
| **Típico (calidad alta + ultra + remesh + PBR 2k)** | **~35**  |

El dashboard muestra el estimado antes de enviar y el consumo real al terminar.

## Limitaciones

- **La asimetría y la forma no se arreglan en post-proceso.** El QA las detecta y
  las reporta, pero la corrección es regenerar con mas vistas o trabajo manual.
- El Smart Project empaqueta peor que un unwrap hecho a mano (~20–45% vs ~50%+).
  Para assets hero conviene el unwrap manual.
- El modelo sale como una sola malla sin materiales: la asignación por partes
  (madera / tela / metal) sigue siendo trabajo manual en Unity.
- Sincronizar con Unity crea el asset una vez. Volver a publicar un producto ya sincronizado
  (por ejemplo tras reprocesarlo) como **nueva versión** del asset todavía no esta resuelto.
  Quitar un producto de un proyecto tampoco lo desenlaza en Unity.
- Un trabajo interrumpido por reiniciar el servidor queda en `FAILED`; se retoma
  con **Reprocesar**. Si el modelo ya esta en `raw/`, Reprocesar **nunca**
  vuelve a llamar a la API: la decisión se toma mirando el archivo en disco.
