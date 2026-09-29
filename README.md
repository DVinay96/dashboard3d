# Pipeline 3D

Pipeline local: **fotos de producto → modelo 3D listo para Unity**, con control de calidad automático.

Resuelve el problema concreto de bajar el output crudo del generador (millones de triángulos,
sin UVs, sin escala real) en lugar de un asset de producción.

```
fotos ──► generador 3D ──► Blender headless ──► QA ──► GLB + FBX
          (flags        (escala real,        (11 checks     (+ copia opcional
           correctos)    pivote, UVs,         + renders)      a Unity)
                         budget de tris)
```

---

## Requisitos

- **Python 3.8+** — sin dependencias externas, solo la librería estándar
- **Blender 4.x o 5.x** — se detecta solo en las rutas habituales
- **API key del generador 3D** — solo si vas a generar desde fotos

## Arranque

```bash
./run.sh
```

Abrí <http://127.0.0.1:8765>. El servidor escucha **únicamente en 127.0.0.1**.

### API key

La key se lee **solo** de la variable de entorno `MESHY_API_KEY`, que el servidor
toma de `.env` al arrancar. La interfaz web no puede guardarla ni mostrarla, y no
se escribe en `data/`. Para cargarla:

```bash
cp .env.example .env   # y completá MESHY_API_KEY=...
chmod 600 .env
```

`.env` está en `.gitignore`. Para cambiar la key, editá el archivo y reiniciá el
servidor — Ajustes solo muestra si está cargada y sus últimos 4 caracteres.

---

## Dos modos de uso

### 1. Desde fotos (consume créditos)

Arrastrá **1 a 4 fotos** del producto. La primera es la vista frontal.

| Fotos | Endpoint | Qué aporta |
|---|---|---|
| 1 | `/image-to-3d` | Incluye `auto_size` + `origin_at:bottom`: escala real y pivote resueltos en origen |
| 2–4 | `/multi-image-to-3d` | **Mucha menos asimetría**: el modelo deja de inventar las caras que no ve |

Con 2–4 vistas la escala y el pivote los corrige Blender después, porque esos dos
parámetros no existen en el endpoint multi-imagen.

**Recomendación:** 3 fotos (frente, lado, atrás). La asimetría es el defecto que
ningún post-proceso arregla, y las vistas extra son la única palanca real contra ella.

### 2. Desde un modelo existente (gratis)

Arrastrá un `.glb` y se saltea la generación: solo corre acondicionado + QA. Sirve para
probar el pipeline sin gastar créditos y para pasar assets del equipo 3D o de
catálogo por el mismo control de calidad.

---

## Qué hace el paso de Blender

1. Aplica las transformaciones heredadas del import
2. Escala a la **altura real en metros** que indicaste
3. Mueve el **pivote a base-centro** (el modelo queda parado en el piso, en el origen)
4. Decima al **budget de triángulos**
5. Genera **UVs** si faltan (Smart Project)
6. Genera el **canal UV2 de lightmap** para el bake de GI en Unity
7. Shade smooth por ángulo (40°)
8. Exporta **GLB** + **FBX** con los ejes de Unity (`-Z` forward, `Y` up, escala 1.0)

> **Detalle no obvio:** si el modelo ya traía UVs y se decima fuerte, el collapse
> las deja con islas superpuestas y caras invertidas. El script las descarta y
> rehace el unwrap. Sin esto, el asset sale con la textura repetida — lo verificamos
> midiendo 138% de área UV acumulada antes del fix.

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

Cada producto pertenece a una marca y lleva metadatos. El esquema tiene dos niveles:

- **Campos base** — iguales para todas las marcas. Vienen con SKU, nombre comercial
  y precio; se editan en **Marcas → Campos base**.
- **Campos propios de la marca** — se suman a los base. No pueden repetir sus claves.

Tipos disponibles: texto, número, lista (opciones separadas por coma), sí/no y fecha.
Cada campo puede ser obligatorio y tener un valor por defecto.

Una marca también guarda **valores por defecto del pipeline** (altura real, budget de
tris, topología, resolución y prompt de textura). Al elegirla en el formulario, esos
valores se cargan solos junto con sus campos ya completados con los defaults.

Lo guardado vive en `data/brands.json`. Las claves se derivan del nombre visible con
los acentos transliterados: "Colección" → `coleccion`.

Al terminar el QA se escribe un **sidecar** `out/<slug>.metadata.json` junto al GLB y
el FBX, con la marca, todos los campos y qué modelos se exportaron. Si configuraste
la carpeta de Unity, viaja con los modelos.

Una marca en uso no se puede borrar: el servidor responde qué productos la usan.

## Los checks de QA

| Check | Falla cuando |
|---|---|
| `polycount` | 50% por encima del budget |
| `uv` | no hay UVs |
| `uv2` | falta el canal de lightmap *(aviso)* |
| `uv_overlap` | área UV acumulada > 101% → islas superpuestas |
| `uv_packing` | aprovechamiento < 25% *(aviso)* |
| `uv_flipped` | caras con UV invertida |
| `scale` | altura fuera del ±2% del objetivo |
| `pivot` | la base no está en Z=0 |
| `pivot_xy` | descentrado en XY *(aviso)* |
| `symmetry` | error de espejado > 2% promedio u 8% pico |
| `slivers` | > 40% de triángulos degenerados *(aviso)* |
| `textures` | UVs regeneradas en un modelo texturizado sin re-hornear |

Si el modelo tiene textura, además de los renders en gris se generan `tex_q34` y
`tex_front` con los materiales reales: el render gris no muestra errores de textura.

### Sobre el check de simetría

Es el que detecta la geometría alucinada. No mide el bounding box (centrar el pivote
lo vuelve simétrico por construcción y el check quedaría siempre en verde): espeja
cada vértice contra el plano YZ y mide la distancia al vecino más cercano con un KD-tree.

Se mide sobre el **modelo original**, no sobre el decimado, porque el collapse colapsa
vértices distinto en cada lado e introduce falsos positivos.

El promedio se diluye porque la mayor parte de un objeto suele ser simétrica, así que
**el pico es la señal real**. Medido sobre los dos modelos de referencia:

| | promedio | pico | veredicto |
|---|---|---|---|
| Modelo crudo generado | 0.45% | **5.8%** | aviso — asimetría localizada |
| Asset del equipo 3D | 0.36% | 2.8% | ok |

---

## Resultados medidos

Corriendo el modo modelo local sobre los dos archivos de referencia:

| | Modelo crudo | → acondicionado | Asset 3D | → acondicionado |
|---|---|---|---|---|
| Triángulos | 3,122,006 | **15,000** | 164,774 | **14,999** |
| Peso | 53.6 MB | **1.9 MB** | 4.8 MB | 1.9 MB |
| Canales UV | ninguno | **UVMap + Lightmap** | UVMap | UVMap + Lightmap |
| Altura | 1.90 u | **0.850 m** | 0.828 m | 0.850 m |
| Base en Z | −0.952 | **−0.0002** | −0.003 | −0.0002 |
| Superficie | 8.68 m² | 1.73 m² | 1.71 m² | 1.73 m² |

La superficie convergente (1.73 vs 1.71 m²) confirma que la escala quedó bien.

---

## Estructura

```
server.py            servidor HTTP + cliente del generador + cola de trabajos
brands.py            catalogo de marcas y esquema de metadatos
qa_blender.py        acondicionado + métricas + renders (corre dentro de Blender)
static/index.html    dashboard
data/
  config.json        API key y rutas (chmod 600, no versionar)
  products/<id>/
    meta.json        estado del producto
    input/           fotos originales
    raw/             lo que devolvió el generador (GLB, FBX, texturas)
    out/             GLB + FBX acondicionados  ← esto va a Unity
    qa/              metrics.json + renders
    log.txt
```

## Import en Unity

Los FBX salen con los ejes correctos, así que en el importer:

- **Scale Factor** 1, **Convert Units** off
- **Generate Lightmap UVs** off (ya viene el canal UV2)
- **Read/Write** off salvo que necesites modificar la malla en runtime
- **Mesh Compression** medium para props de fondo

Si completás la carpeta de Unity en Ajustes, cada modelo que pase el QA en verde
se copia ahí automáticamente.

---

## Costos de generación

| Concepto | Créditos |
|---|---|
| Base con textura 2k/4k | 30 |
| Textura 8k | 35 |
| Ultra mode (calidad alta) | +5 |
| Remesh | +5 |
| **Típico (calidad alta + ultra + remesh + PBR 2k)** | **~35** |

El dashboard muestra el estimado antes de enviar y el consumo real al terminar.

## Limitaciones

- **La asimetría y la forma no se arreglan en post-proceso.** El QA las detecta y
  las reporta, pero la corrección es regenerar con más vistas o trabajo manual.
- El Smart Project empaqueta peor que un unwrap hecho a mano (~20–45% vs ~50%+).
  Para assets hero conviene el unwrap manual.
- El modelo sale como una sola malla sin materiales: la asignación por partes
  (madera / tela / metal) sigue siendo trabajo manual en Unity.
- Un trabajo interrumpido por reiniciar el servidor queda en `FAILED`; se retoma
  con **Reprocesar**. Si el modelo ya está en `raw/`, Reprocesar **nunca**
  vuelve a llamar a la API: la decisión se toma mirando el archivo en disco.
