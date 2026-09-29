#!/usr/bin/env python3
"""
Acondicionado + QA de un modelo, ejecutado dentro de Blender headless.

  blender -b --factory-startup -noaudio --python qa_blender.py -- '<json>'

json = {src, out_dir, qa_dir, slug, target_height_m, tri_budget, lightmap_uv, export_fbx}

Escribe <qa_dir>/metrics.json con metricas antes/despues y la lista de checks,
renders de 4 vistas + wireframe + layout de UVs, y exporta GLB/FBX a <out_dir>.
"""

import json
import math
import os
import sys

import bpy
import bmesh
import mathutils

try:
    import numpy as np
except Exception:
    np = None


# ---------------------------------------------------------------- utilidades


def log(msg):
    print("[qa] %s" % msg, flush=True)


def mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def world_bbox(objs):
    lo = mathutils.Vector((1e18, 1e18, 1e18))
    hi = mathutils.Vector((-1e18, -1e18, -1e18))
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    return lo, hi


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def measure(objs, label):
    """Metricas agregadas de una lista de objetos mesh."""
    m = {
        "label": label,
        "objects": len(objs),
        "verts": 0,
        "tris": 0,
        "quads": 0,
        "ngons": 0,
        "faces": 0,
        "loose_parts": 0,
        "boundary_edges": 0,
        "non_manifold_edges": 0,
        "uv_layers": [],
        "materials": [],
        "surface_area_m2": 0.0,
        "sliver_pct": 0.0,
        "degenerate_faces": 0,
    }
    qsum = []
    for o in objs:
        me = o.data
        m["verts"] += len(me.vertices)
        m["faces"] += len(me.polygons)
        for lay in me.uv_layers:
            if lay.name not in m["uv_layers"]:
                m["uv_layers"].append(lay.name)
        for mat in me.materials:
            if mat and mat.name not in m["materials"]:
                m["materials"].append(mat.name)

        sx, sy, sz = o.matrix_world.to_scale()
        area_scale = abs(sx * sy)  # aproximacion suficiente para escala uniforme
        for p in me.polygons:
            n = len(p.vertices)
            if n == 3:
                m["tris"] += 1
            elif n == 4:
                m["quads"] += 1
            else:
                m["ngons"] += 1
            m["surface_area_m2"] += p.area * area_scale
            if p.area < 1e-12:
                m["degenerate_faces"] += 1

        bm = bmesh.new()
        bm.from_mesh(me)
        m["boundary_edges"] += sum(1 for e in bm.edges if e.is_boundary)
        m["non_manifold_edges"] += sum(1 for e in bm.edges if not e.is_manifold)

        # partes sueltas
        seen = set()
        for v in bm.verts:
            if v.index in seen:
                continue
            m["loose_parts"] += 1
            stack = [v]
            seen.add(v.index)
            while stack:
                x = stack.pop()
                for e in x.link_edges:
                    ov = e.other_vert(x)
                    if ov.index not in seen:
                        seen.add(ov.index)
                        stack.append(ov)

        # calidad de triangulo (1 = equilatero)
        for f in bm.faces:
            if len(f.verts) != 3:
                continue
            a = (f.verts[0].co - f.verts[1].co).length
            b = (f.verts[1].co - f.verts[2].co).length
            c = (f.verts[2].co - f.verts[0].co).length
            den = a * a + b * b + c * c
            if den <= 0:
                continue
            s = (a + b + c) / 2.0
            ar2 = max(s * (s - a) * (s - b) * (s - c), 0.0)
            qsum.append(4 * math.sqrt(3) * math.sqrt(ar2) / den)
        bm.free()

    if qsum:
        m["sliver_pct"] = round(100.0 * sum(1 for q in qsum if q < 0.2) / len(qsum), 2)
        m["tri_quality_mean"] = round(sum(qsum) / len(qsum), 3)

    lo, hi = world_bbox(objs) if objs else (mathutils.Vector(), mathutils.Vector())
    m["bbox_min"] = [round(v, 5) for v in lo]
    m["bbox_max"] = [round(v, 5) for v in hi]
    m["dimensions_m"] = [round(hi[i] - lo[i], 4) for i in range(3)]
    m["surface_area_m2"] = round(m["surface_area_m2"], 4)
    return m


def mirror_symmetry(objs, samples=20000):
    """Simetria geometrica real respecto del plano YZ que pasa por el centro.

    Espeja cada vertice y mide la distancia al vecino mas cercano del original.
    Devuelve el error medio normalizado por el tamano del objeto (0 = simetrico).
    Es el check que detecta la cara que la IA invento sin haberla visto.
    """
    pts = []
    for o in objs:
        mw = o.matrix_world
        vs = o.data.vertices
        step = max(1, len(vs) // max(1, samples // max(1, len(objs))))
        for i in range(0, len(vs), step):
            pts.append(mw @ vs[i].co)
    if len(pts) < 50:
        return None

    lo = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    size = max(max(hi[i] - lo[i] for i in range(3)), 1e-9)
    cx = (lo.x + hi.x) / 2.0

    try:
        from mathutils import kdtree
    except Exception:
        return None
    tree = kdtree.KDTree(len(pts))
    for i, p in enumerate(pts):
        tree.insert(p, i)
    tree.balance()

    total = 0.0
    worst = 0.0
    for p in pts:
        m = mathutils.Vector((2 * cx - p.x, p.y, p.z))
        _, _, d = tree.find(m)
        total += d
        worst = max(worst, d)
    mean = total / len(pts)
    return {
        "mean_error_pct": round(100.0 * mean / size, 2),
        "max_error_pct": round(100.0 * worst / size, 2),
        "samples": len(pts),
    }


def uv_stats(objs):
    """Aprovechamiento del espacio UV y caras invertidas."""
    tot_uv = 0.0
    flipped = 0
    umin = vmin = 1e9
    umax = vmax = -1e9
    faces = 0
    for o in objs:
        me = o.data
        if not me.uv_layers:
            continue
        uvl = me.uv_layers[0].data
        for p in me.polygons:
            li = list(p.loop_indices)
            if len(li) < 3:
                continue
            faces += 1
            a = uvl[li[0]].uv
            b = uvl[li[1]].uv
            c = uvl[li[2]].uv
            cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cr < 0:
                flipped += 1
            tot_uv += abs(cr) / 2.0
            for uv in (a, b, c):
                umin = min(umin, uv[0]); umax = max(umax, uv[0])
                vmin = min(vmin, uv[1]); vmax = max(vmax, uv[1])
    if faces == 0:
        return None
    return {
        "packing_pct": round(tot_uv * 100, 1),
        "flipped_faces": flipped,
        "u_range": [round(umin, 4), round(umax, 4)],
        "v_range": [round(vmin, 4), round(vmax, 4)],
    }


# --------------------------------------------------------------------- bake


def has_textures(objs):
    for o in objs:
        for m in o.data.materials:
            if m and m.use_nodes and any(n.type == "TEX_IMAGE" and n.image for n in m.node_tree.nodes):
                return True
    return False


def _principled_and_output(mat):
    """Busca los nodos en el momento: no guardar referencias entre cambios del arbol."""
    if not (mat and mat.use_nodes):
        return None, None
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    outs = [n for n in nodes if n.type == "OUTPUT_MATERIAL"]
    out = next((n for n in outs if n.is_active_output), outs[0] if outs else None)
    return bsdf, out


def _bake_image(name, res, non_color):
    img = bpy.data.images.new(name, width=res, height=res, alpha=False)
    if non_color:
        try:
            img.colorspace_settings.name = "Non-Color"
        except Exception:
            pass
    return img


def bake_high_to_low(highs, low, cfg):
    """Transfiere las texturas del modelo original (high) al decimado (low).

    La textura de Meshy esta pintada para SUS UVs. Si el decimate obliga a
    rehacer las UVs, reusar la imagen original produce un mosaico sin sentido:
    cada cara lee una zona equivocada. Lo correcto es hornear de nuevo.

    Base color, roughness y metallic se hornean con el truco de emision (valor
    exacto, sin iluminacion); la normal se hornea en espacio tangente e incluye
    el normal map del original, asi se conserva el detalle que quito el decimate.
    """
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        sc.cycles.device = "CPU"
        sc.cycles.samples = 4
    except Exception:
        pass
    prev_view = sc.view_settings.view_transform
    try:
        sc.view_settings.view_transform = "Standard"
    except Exception:
        pass
    try:
        return _bake(highs, low, cfg, sc)
    finally:
        # si queda en Standard, los renders con textura salen quemados
        sc.view_settings.view_transform = prev_view


def _bake(highs, low, cfg, sc):
    res = int(cfg.get("bake_resolution") or 2048)
    out_dir = cfg["out_dir"]
    slug = cfg.get("slug") or "modelo"
    lo, hi = world_bbox([low])
    size = max(max(hi[i] - lo[i] for i in range(3)), 1e-3)

    # material destino, propio del low (no compartido con el high)
    low.data.materials.clear()
    mat = bpy.data.materials.new(slug + "_baked")
    mat.use_nodes = True
    low.data.materials.append(mat)

    high_mats = []
    for h in highs:
        for m in h.data.materials:
            if m and m not in high_mats:
                high_mats.append(m)

    bpy.ops.object.select_all(action="DESELECT")
    for h in highs:
        h.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low

    common = dict(
        use_selected_to_active=True,
        cage_extrusion=size * 0.02,
        max_ray_distance=size * 0.06,
        margin=16,
    )

    def add_target(img):
        nt = mat.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node
        return node.name

    baked = {}
    for key, socket, non_color in (
        ("basecolor", "Base Color", False),
        ("roughness", "Roughness", True),
        ("metallic", "Metallic", True),
    ):
        img = _bake_image("%s_%s" % (slug, key), res, non_color)
        node_name = add_target(img)

        # truco de emision: el canal pedido va directo a la salida del material
        patched = []
        for m in high_mats:
            mnt = m.node_tree
            em = mnt.nodes.new("ShaderNodeEmission")
            em_name = em.name
            bsdf, out = _principled_and_output(m)
            if not (bsdf and out):
                mnt.nodes.remove(mnt.nodes[em_name])
                continue
            em = mnt.nodes[em_name]
            em.inputs["Strength"].default_value = 1.0
            inp = bsdf.inputs[socket]
            if inp.is_linked:
                mnt.links.new(inp.links[0].from_socket, em.inputs["Color"])
            else:
                v = inp.default_value
                try:
                    em.inputs["Color"].default_value = (v[0], v[1], v[2], 1.0)
                except TypeError:
                    em.inputs["Color"].default_value = (v, v, v, 1.0)
            prev = [(l.from_node.name, l.from_socket.identifier) for l in out.inputs["Surface"].links]
            mnt.links.new(em.outputs["Emission"], out.inputs["Surface"])
            patched.append((m, em_name, prev))
        try:
            bpy.ops.object.bake(type="EMIT", **common)
        finally:
            for m, em_name, prev in patched:
                mnt = m.node_tree
                if em_name in mnt.nodes:
                    mnt.nodes.remove(mnt.nodes[em_name])
                _, out = _principled_and_output(m)
                for node_name_prev, ident in prev:
                    src = mnt.nodes.get(node_name_prev)
                    sock = next((s for s in src.outputs if s.identifier == ident), None) if src else None
                    if sock and out:
                        mnt.links.new(sock, out.inputs["Surface"])
        baked[key] = (img, node_name)
        log("horneado %s %dpx" % (key, res))

    img = _bake_image("%s_normal" % slug, res, True)
    node_name = add_target(img)
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", **common)
    baked["normal"] = (img, node_name)
    log("horneado normal %dpx" % res)

    # guardar y conectar el material final
    files = []
    for key, (img, _) in baked.items():
        path = os.path.join(out_dir, "%s_%s.png" % (slug, key))
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        files.append(os.path.basename(path))

    nt = mat.node_tree
    bsdf, _ = _principled_and_output(mat)
    tex = lambda k: nt.nodes[baked[k][1]].outputs["Color"]
    nt.links.new(tex("basecolor"), bsdf.inputs["Base Color"])
    nt.links.new(tex("roughness"), bsdf.inputs["Roughness"])
    nt.links.new(tex("metallic"), bsdf.inputs["Metallic"])
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.uv_map = low.data.uv_layers[0].name
    nt.links.new(tex("normal"), nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return files


# ------------------------------------------------------------- acondicionado


def condition(objs, cfg):
    """Escala real, pivote en la base, budget de poligonos, UVs, smooth."""
    actions = []

    # 1. aplicar transformaciones heredadas del import
    select_only(objs)
    try:
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        actions.append("Transformaciones aplicadas (rotacion + escala)")
    except Exception as e:
        log("transform_apply fallo: %s" % e)

    # 2. escala a altura real
    target_h = float(cfg.get("target_height_m") or 0)
    lo, hi = world_bbox(objs)
    cur_h = hi.z - lo.z
    if target_h > 0 and cur_h > 1e-6:
        f = target_h / cur_h
        if abs(f - 1.0) > 0.005:
            for o in objs:
                o.scale = (o.scale[0] * f, o.scale[1] * f, o.scale[2] * f)
            bpy.context.view_layer.update()
            select_only(objs)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            actions.append("Escalado x%.4f -> altura %.3f m" % (f, target_h))

    # 3. pivote: centro en XY, base en Z=0
    lo, hi = world_bbox(objs)
    off = mathutils.Vector((-(lo.x + hi.x) / 2.0, -(lo.y + hi.y) / 2.0, -lo.z))
    if off.length > 1e-5:
        for o in objs:
            o.location = o.location + off
        bpy.context.view_layer.update()
        select_only(objs)
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        actions.append("Pivote movido a base-centro (offset %.3f m)" % off.length)

    # 4. budget de triangulos
    #    OJO: el collapse decimate arrastra las UVs y genera islas superpuestas
    #    y caras invertidas. Si el modelo YA tenia UVs y lo decimamos fuerte,
    #    hay que rehacer el unwrap; conservarlas da un layout roto.
    #    Si ademas tiene TEXTURAS, rehacer las UVs sin volver a hornear rompe la
    #    textura (mosaico). En ese caso se guarda una copia del original y se
    #    hornea high -> low despues del unwrap.
    budget = int(cfg.get("tri_budget") or 0)
    had_uv = [o for o in objs if o.data.uv_layers]
    textured = has_textures(objs)
    state = cfg.setdefault("_state", {})
    state.update(textured=textured, decimated=False, baked=False, uv_regenerated=False)
    needs_reuv = []
    highs = []
    if budget > 0:
        total = sum(len(o.data.polygons) for o in objs)
        if total > budget:
            ratio = float(budget) / total
            state["decimated"] = True
            if textured and cfg.get("bake_textures", True):
                for o in objs:
                    h = o.copy()
                    h.data = o.data.copy()
                    h.name = o.name + "_high"
                    bpy.context.scene.collection.objects.link(h)
                    highs.append(h)
                if len(objs) > 1:
                    select_only(objs)
                    bpy.ops.object.join()
                    objs = [bpy.context.view_layer.objects.active]
                    actions.append("Partes unidas en una malla para un solo set de texturas")
            for o in objs:
                bpy.context.view_layer.objects.active = o
                mod = o.modifiers.new("qa_decimate", "DECIMATE")
                mod.decimate_type = "COLLAPSE"
                mod.ratio = ratio
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except Exception as e:
                    log("decimate fallo en %s: %s" % (o.name, e))
            actions.append("Decimado %d -> ~%d tris (ratio %.3f)" % (total, budget, ratio))
            if highs:
                needs_reuv = list(objs)
            elif ratio < 0.9 and not textured and cfg.get("reuv_after_decimate", True):
                needs_reuv = [o for o in objs if o.data.uv_layers]
            elif textured:
                actions.append("AVISO: textura sin re-hornear; las UVs quedan deformadas por el decimate")

    # 4b. rehacer UVs arruinadas por el decimate
    if needs_reuv:
        for o in needs_reuv:
            while len(o.data.uv_layers) > 0:
                o.data.uv_layers.remove(o.data.uv_layers[0])
        state["uv_regenerated"] = True
        actions.append("UVs descartadas tras el decimate (el collapse las deja superpuestas)")

    # 5. UV principal (con mas margen entre islas si se va a hornear)
    missing = [o for o in objs if not o.data.uv_layers]
    if missing:
        select_only(missing)
        try:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(
                angle_limit=math.radians(66),
                island_margin=0.01 if highs else 0.003,
            )
            bpy.ops.object.mode_set(mode="OBJECT")
            actions.append("UV generada con Smart Project en %d objeto/s" % len(missing))
        except Exception as e:
            log("smart_project fallo: %s" % e)
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                pass

    # 5b. hornear texturas del original sobre las UVs nuevas
    if highs:
        try:
            files = bake_high_to_low(highs, objs[0], cfg)
            state["baked"] = True
            state["baked_files"] = files
            actions.append("Texturas re-horneadas high->low: %s" % ", ".join(files))
        except Exception as e:
            log("bake fallo: %s" % e)
            actions.append("ERROR: el bake de texturas fallo (%s)" % e)
        finally:
            for h in highs:
                me = h.data
                bpy.data.objects.remove(h, do_unlink=True)
                if me.users == 0:
                    bpy.data.meshes.remove(me)

    # 6. segundo canal UV para lightmaps de Unity
    if cfg.get("lightmap_uv"):
        made = 0
        for o in objs:
            if len(o.data.uv_layers) >= 2:
                continue
            try:
                o.data.uv_layers.new(name="Lightmap")
                o.data.uv_layers.active_index = len(o.data.uv_layers) - 1
                select_only([o])
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.lightmap_pack(PREF_MARGIN_DIV=0.2)
                bpy.ops.object.mode_set(mode="OBJECT")
                # la textura debe seguir leyendo del canal 0, no del lightmap
                o.data.uv_layers.active_index = 0
                o.data.uv_layers[0].active_render = True
                made += 1
            except Exception as e:
                log("lightmap_pack fallo en %s: %s" % (o.name, e))
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except Exception:
                    pass
        if made:
            actions.append("Canal UV2 de lightmap generado en %d objeto/s" % made)

    # 7. sombreado suave por angulo
    select_only(objs)
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
        actions.append("Shade smooth por angulo (40 grados)")
    except Exception:
        try:
            bpy.ops.object.shade_smooth()
            actions.append("Shade smooth")
        except Exception as e:
            log("shade smooth fallo: %s" % e)

    return actions


# -------------------------------------------------------------------- checks


def build_checks(after, uvs, cfg, before=None):
    c = []

    def add(level, key, msg):
        c.append({"level": level, "key": key, "msg": msg})

    budget = int(cfg.get("tri_budget") or 0)
    tris = after["tris"] + after["quads"] * 2 + after["ngons"] * 2
    if budget:
        if tris > budget * 1.5:
            add("fail", "polycount", "%s tris, %.0f%% por encima del budget de %s" % (f"{tris:,}", 100.0 * tris / budget - 100, f"{budget:,}"))
        elif tris > budget:
            add("warn", "polycount", "%s tris, apenas por encima del budget de %s" % (f"{tris:,}", f"{budget:,}"))
        else:
            add("pass", "polycount", "%s tris dentro del budget de %s" % (f"{tris:,}", f"{budget:,}"))

    if not after["uv_layers"]:
        add("fail", "uv", "Sin UVs: no se puede texturizar ni hacer bake de lightmaps")
    else:
        add("pass", "uv", "UVs presentes: %s" % ", ".join(after["uv_layers"]))
        if len(after["uv_layers"]) >= 2:
            add("pass", "uv2", "Canal UV2 listo para lightmaps de Unity")
        else:
            add("warn", "uv2", "Sin segundo canal UV: Unity va a tener que generarlo al importar")

    if uvs:
        # >100% de area acumulada implica islas superpuestas: dos zonas del
        # modelo comparten el mismo texel y la textura se va a ver repetida.
        if uvs["packing_pct"] > 101:
            add("fail", "uv_overlap", "Islas UV superpuestas (area acumulada %.1f%%): la textura se va a repetir" % uvs["packing_pct"])
        elif uvs["packing_pct"] < 25:
            add("warn", "uv_packing", "Aprovechamiento del espacio UV %.1f%%: se desperdicia resolucion de textura" % uvs["packing_pct"])
        else:
            add("pass", "uv_packing", "Aprovechamiento del espacio UV %.1f%%" % uvs["packing_pct"])
        if uvs["u_range"][0] < -0.001 or uvs["u_range"][1] > 1.001 or uvs["v_range"][0] < -0.001 or uvs["v_range"][1] > 1.001:
            add("warn", "uv_range", "UVs fuera del rango 0-1 (u %s, v %s)" % (uvs["u_range"], uvs["v_range"]))
        if uvs["flipped_faces"] > 0:
            lvl = "warn" if uvs["flipped_faces"] < after["faces"] * 0.02 else "fail"
            add(lvl, "uv_flipped", "%d caras con UV invertida" % uvs["flipped_faces"])

    h = after["dimensions_m"][2]
    target_h = float(cfg.get("target_height_m") or 0)
    if target_h > 0:
        if abs(h - target_h) > target_h * 0.02:
            add("fail", "scale", "Altura %.3f m, se esperaba %.3f m" % (h, target_h))
        else:
            add("pass", "scale", "Altura %.3f m (objetivo %.3f m)" % (h, target_h))
    else:
        if h < 0.02 or h > 20:
            add("warn", "scale", "Altura %.3f m: revisar, parece fuera de escala real" % h)
        else:
            add("pass", "scale", "Altura %.3f m, escala plausible" % h)

    zmin = after["bbox_min"][2]
    if abs(zmin) > 0.01:
        add("fail", "pivot", "El pivote no esta en la base (base en z=%.3f m)" % zmin)
    else:
        add("pass", "pivot", "Pivote en la base, apoyado en el piso")

    cx = (after["bbox_min"][0] + after["bbox_max"][0]) / 2.0
    cy = (after["bbox_min"][1] + after["bbox_max"][1]) / 2.0
    if abs(cx) > 0.02 or abs(cy) > 0.02:
        add("warn", "pivot_xy", "Pivote descentrado en XY (%.3f, %.3f)" % (cx, cy))
    else:
        add("pass", "pivot_xy", "Pivote centrado en XY")

    # simetria geometrica real (no del bounding box: centrar el pivote lo
    # vuelve simetrico por construccion y el check quedaria siempre en verde)
    #    El promedio se diluye porque la mayor parte del objeto suele ser
    #    simetrica: el pico es la senal que delata la zona alucinada.
    #    Se mide sobre el modelo ORIGINAL: el decimate introduce ruido que
    #    dispara falsos positivos (colapsa vertices distinto en cada lado).
    sym = (before or {}).get("symmetry") or after.get("symmetry")
    if sym:
        e, mx = sym["mean_error_pct"], sym["max_error_pct"]
        if e > 2.0 or mx > 8.0:
            add("fail", "symmetry", "Asimetria izquierda/derecha: %.2f%% promedio, %.1f%% en el peor punto. La IA invento la cara que no vio en la foto." % (e, mx))
        elif e > 0.8 or mx > 4.0:
            add("warn", "symmetry", "Asimetria localizada: %.2f%% promedio pero %.1f%% en el peor punto. Revisa esa zona en los renders." % (e, mx))
        else:
            add("pass", "symmetry", "Simetria izquierda/derecha correcta (%.2f%% promedio, %.1f%% pico)" % (e, mx))

    if after["sliver_pct"] > 40:
        add("warn", "slivers", "%.1f%% de triangulos degenerados/slivers" % after["sliver_pct"])
    else:
        add("pass", "slivers", "%.1f%% de slivers" % after["sliver_pct"])

    if after["degenerate_faces"] > 0:
        add("warn", "degenerate", "%d caras de area cero" % after["degenerate_faces"])

    st = cfg.get("_state") or {}
    if st.get("textured"):
        if st.get("baked"):
            add("pass", "textures", "Texturas re-horneadas sobre las UVs nuevas (%s)" % ", ".join(st.get("baked_files", [])))
        elif st.get("uv_regenerated"):
            add("fail", "textures", "UVs regeneradas sin re-hornear: la textura se va a ver como un mosaico")
        elif st.get("decimated"):
            add("warn", "textures", "Decimado sin re-hornear: la textura puede verse estirada. Subi el budget o activa el bake")
        else:
            add("pass", "textures", "Texturas originales intactas (sin decimar, UVs de origen)")

    add("info", "parts", "%d parte/s suelta/s, %d objeto/s" % (after["loose_parts"], after["objects"]))
    if not after["materials"]:
        add("warn", "materials", "Sin materiales: hay que asignarlos en Unity")
    else:
        add("pass", "materials", "%d material/es: %s" % (len(after["materials"]), ", ".join(after["materials"][:6])))

    return c


# ------------------------------------------------------------------- renders


def setup_render(objs, res=(560, 680)):
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            sc.render.engine = eng
            break
        except Exception:
            continue
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"

    world = bpy.data.worlds.new("qa_world")
    sc.world = world
    world.use_nodes = True
    bgn = world.node_tree.nodes.get("Background")
    if bgn:
        bgn.inputs[0].default_value = (0.055, 0.058, 0.07, 1)
        bgn.inputs[1].default_value = 1.0

    lo, hi = world_bbox(objs)
    ctr = (lo + hi) / 2.0
    size = max(max(hi[i] - lo[i] for i in range(3)), 1e-3)

    def area_light(loc, energy, sz):
        d = bpy.data.lights.new("l", type="AREA")
        d.energy = energy
        d.size = sz
        ob = bpy.data.objects.new("l", d)
        sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (ctr - mathutils.Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    k = size * size
    area_light((ctr.x + size * 2, ctr.y - size * 2, ctr.z + size * 2.2), 2200 * k, size * 2)
    area_light((ctr.x - size * 2.5, ctr.y - size * 1.4, ctr.z + size * 0.9), 800 * k, size * 2)
    area_light((ctr.x, ctr.y + size * 3, ctr.z + size * 1.6), 1000 * k, size * 2)

    cam_d = bpy.data.cameras.new("qa_cam")
    cam_d.lens = 72
    cam = bpy.data.objects.new("qa_cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam, ctr, size


VIEWS = {
    "q34": (-0.9, -0.9, 0.45),
    "front": (0, -1, 0.22),
    "side": (1, 0, 0.2),
    "back": (0.6, 0.9, 0.35),
}


def render_views(objs, qa_dir, wire=False, textured=False):
    cam, ctr, size = setup_render(objs)
    sc = bpy.context.scene
    made = []

    # render con los materiales reales: el clay no muestra problemas de UV/textura
    if textured:
        for name in ("q34", "front"):
            d = mathutils.Vector(VIEWS[name]).normalized() * size * 2.55
            cam.location = ctr + d
            cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = os.path.join(qa_dir, "tex_" + name + ".png")
            bpy.ops.render.render(write_still=True)
            made.append("tex_" + name + ".png")

    clay = bpy.data.materials.new("qa_clay")
    clay.use_nodes = True
    bsdf = clay.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.63, 0.63, 0.65, 1)
        bsdf.inputs["Roughness"].default_value = 0.48
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(clay)

    for name, v in VIEWS.items():
        d = mathutils.Vector(v).normalized() * size * 2.55
        cam.location = ctr + d
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(qa_dir, name + ".png")
        bpy.ops.render.render(write_still=True)
        made.append(name + ".png")

    if wire:
        try:
            # show_wire es solo overlay de viewport y no sale en el render:
            # hay que usar el nodo Wireframe dentro del material.
            wm = bpy.data.materials.new("qa_wire")
            wm.use_nodes = True
            nt = wm.node_tree
            for n in list(nt.nodes):
                if n.bl_idname != "ShaderNodeOutputMaterial":
                    nt.nodes.remove(n)
            # re-buscar DESPUES de borrar: la referencia previa queda colgada
            out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
            wire_n = nt.nodes.new("ShaderNodeWireframe")
            wire_n.use_pixel_size = True
            wire_n.inputs["Size"].default_value = 1.1
            base = nt.nodes.new("ShaderNodeEmission")
            base.inputs["Color"].default_value = (0.10, 0.12, 0.17, 1)
            edge = nt.nodes.new("ShaderNodeEmission")
            edge.inputs["Color"].default_value = (0.36, 0.86, 0.72, 1)
            mix = nt.nodes.new("ShaderNodeMixShader")
            fac_out = wire_n.outputs.get("Factor") or wire_n.outputs[0]
            nt.links.new(fac_out, mix.inputs[0])
            nt.links.new(base.outputs["Emission"], mix.inputs[1])
            nt.links.new(edge.outputs["Emission"], mix.inputs[2])
            nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
            for o in objs:
                o.data.materials.clear()
                o.data.materials.append(wm)
            d = mathutils.Vector(VIEWS["q34"]).normalized() * size * 2.55
            cam.location = ctr + d
            cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = os.path.join(qa_dir, "wire.png")
            bpy.ops.render.render(write_still=True)
            made.append("wire.png")
        except Exception as e:
            log("wireframe fallo: %s" % e)
    return made


def render_uv_layout(objs, qa_dir, size=640):
    """Rasteriza las aristas de UV a un PNG, sin dependencias externas."""
    if np is None:
        return None
    img = np.zeros((size, size, 4), dtype=np.float32)
    img[:, :, 0:3] = 0.05
    img[:, :, 3] = 1.0
    # grilla
    for g in range(1, 4):
        p = int(size * g / 4.0)
        img[p, :, 0:3] = 0.13
        img[:, p, 0:3] = 0.13

    def line(x0, y0, x1, y1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        if n > 4000:
            return
        for i in range(n + 1):
            t = i / float(n)
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            if 0 <= x < size and 0 <= y < size:
                img[y, x, 0] = 0.45
                img[y, x, 1] = 0.85
                img[y, x, 2] = 0.75

    drawn = 0
    for o in objs:
        me = o.data
        if not me.uv_layers:
            continue
        uvl = me.uv_layers[0].data
        for p in me.polygons:
            li = list(p.loop_indices)
            for i in range(len(li)):
                a = uvl[li[i]].uv
                b = uvl[li[(i + 1) % len(li)]].uv
                line(a[0] * (size - 1), (1 - a[1]) * (size - 1),
                     b[0] * (size - 1), (1 - b[1]) * (size - 1))
            drawn += 1
            if drawn > 60000:
                break
    if drawn == 0:
        return None
    bimg = bpy.data.images.new("uv_layout", width=size, height=size, alpha=True)
    bimg.pixels = img[::-1].ravel().tolist()
    path = os.path.join(qa_dir, "uv.png")
    bimg.filepath_raw = path
    bimg.file_format = "PNG"
    bimg.save()
    return "uv.png"


# ---------------------------------------------------------------------- main


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    cfg = json.loads(argv[0])
    src = cfg["src"]
    out_dir = cfg["out_dir"]
    qa_dir = cfg["qa_dir"]
    slug = cfg.get("slug") or "modelo"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(qa_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    log("importando %s" % src)
    if src.lower().endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=src)
    elif src.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=src)
    elif src.lower().endswith(".obj"):
        try:
            bpy.ops.wm.obj_import(filepath=src)
        except Exception:
            bpy.ops.import_scene.obj(filepath=src)
    else:
        raise SystemExit("formato no soportado: %s" % src)

    objs = mesh_objects()
    if not objs:
        raise SystemExit("el archivo no contiene mallas")
    log("%d objeto/s mesh" % len(objs))

    before = measure(objs, "antes")
    before["uv_stats"] = uv_stats(objs)
    before["symmetry"] = mirror_symmetry(objs)

    actions = condition(objs, cfg)
    for a in actions:
        log(a)

    objs = mesh_objects()
    after = measure(objs, "despues")
    after["uv_stats"] = uv_stats(objs)
    after["symmetry"] = mirror_symmetry(objs)
    checks = build_checks(after, after["uv_stats"], cfg, before)

    # ---- texturas empaquetadas dentro del GLB -> archivos reales ----
    #      El FBX exporter (path_mode=COPY) no puede copiar imagenes empaquetadas
    #      y Unity recibiria un FBX sin texturas.
    for o in objs:
        for m in o.data.materials:
            if not (m and m.use_nodes):
                continue
            for n in m.node_tree.nodes:
                img = n.image if n.type == "TEX_IMAGE" else None
                if not img or img.get("_qa_saved"):
                    continue
                on_disk = img.filepath and os.path.exists(bpy.path.abspath(img.filepath))
                if img.packed_file or not on_disk:
                    path = os.path.join(out_dir, "%s_%s.png" % (slug, bpy.path.clean_name(img.name)))
                    try:
                        img.save(filepath=path)
                        img.filepath = path
                        if img.packed_file:
                            img.unpack(method="USE_ORIGINAL")
                        img["_qa_saved"] = True
                    except Exception as e:
                        log("no se pudo guardar la textura %s: %s" % (img.name, e))

    # ---- export antes de reemplazar materiales por clay ----
    exported = {}
    select_only(objs)
    glb_out = os.path.join(out_dir, slug + ".glb")
    try:
        bpy.ops.export_scene.gltf(
            filepath=glb_out, export_format="GLB", use_selection=True,
            export_yup=True, export_apply=True,
        )
        exported["glb"] = os.path.basename(glb_out)
    except Exception as e:
        log("export glb fallo: %s" % e)

    if cfg.get("export_fbx"):
        fbx_out = os.path.join(out_dir, slug + ".fbx")
        try:
            bpy.ops.export_scene.fbx(
                filepath=fbx_out, use_selection=True,
                axis_forward="-Z", axis_up="Y",
                global_scale=1.0, apply_unit_scale=True,
                bake_space_transform=False, mesh_smooth_type="FACE",
                path_mode="COPY", embed_textures=False,
            )
            exported["fbx"] = os.path.basename(fbx_out)
        except Exception as e:
            log("export fbx fallo: %s" % e)

    # ---- renders (destruyen materiales, van al final) ----
    uv_png = render_uv_layout(objs, qa_dir)
    st = cfg.get("_state") or {}
    renders = render_views(objs, qa_dir, wire=True, textured=has_textures(objs))
    for f in st.get("baked_files", []):
        exported[f.rsplit("_", 1)[-1].replace(".png", "")] = f

    metrics = {
        "source": os.path.basename(src),
        "before": before,
        "after": after,
        "actions": actions,
        "checks": checks,
        "renders": renders,
        "uv_render": uv_png,
        "exported": exported,
        "state": {k: v for k, v in st.items() if k != "baked_files"},
        "summary": {
            "pass": sum(1 for c in checks if c["level"] == "pass"),
            "warn": sum(1 for c in checks if c["level"] == "warn"),
            "fail": sum(1 for c in checks if c["level"] == "fail"),
        },
    }
    with open(os.path.join(qa_dir, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    log("listo: %s" % metrics["summary"])


main()
