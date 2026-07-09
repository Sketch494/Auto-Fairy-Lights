# Auto Fairy Lights - mesh generation core
# Builds ONE low-poly mesh per string: wire tube + bulbs, exact winding,
# separate material slots (wire / glow), UV2 twinkle data, vertex colors.
import math
import random

import bpy
import bmesh
from mathutils import Vector, Quaternion
from mathutils.geometry import interpolate_bezier

WIRE_COLOR = (0.035, 0.03, 0.028, 1.0)
GOLDEN = 2.399963  # golden angle, radians


# ---------------------------------------------------------------- sampling

def sample_curve_polylines(curve_ob):
    """Return list of (points:list[Vector], cyclic:bool) in curve-local space."""
    out = []
    for spline in curve_ob.data.splines:
        pts = []
        cyclic = bool(spline.use_cyclic_u)
        if spline.type == 'BEZIER':
            bp = spline.bezier_points
            if len(bp) < 2:
                continue
            res = max(6, curve_ob.data.resolution_u)
            n_seg = len(bp) if cyclic else len(bp) - 1
            for i in range(n_seg):
                a = bp[i]
                b = bp[(i + 1) % len(bp)]
                seg = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, res)
                if i > 0:
                    seg = seg[1:]
                pts.extend(Vector(p) for p in seg)
        else:  # POLY / NURBS (treated as poly approximation)
            sp = spline.points
            if len(sp) < 2:
                continue
            pts = [Vector(p.co[:3]) for p in sp]
            if cyclic:
                pts.append(pts[0].copy())
        # drop degenerate duplicates
        clean = [pts[0]]
        for p in pts[1:]:
            if (p - clean[-1]).length > 1e-6:
                clean.append(p)
        if len(clean) >= 2:
            out.append((clean, cyclic))
    return out


def _cumlen(pts):
    acc = [0.0]
    for i in range(1, len(pts)):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    return acc


def densify(pts, max_step):
    """Insert points so no segment is longer than max_step (for smooth droop)."""
    out = [pts[0]]
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        d = (b - a).length
        n = max(1, int(math.ceil(d / max_step)))
        for k in range(1, n + 1):
            out.append(a.lerp(b, k / n))
    return out


def apply_droop(pts, droop, interval, down):
    """Sag the polyline between anchors spaced `interval` apart along arc length."""
    if droop <= 0.0:
        return pts
    acc = _cumlen(pts)
    total = acc[-1]
    if total < 1e-6:
        return pts
    out = []
    for p, s in zip(pts, acc):
        seg_i = int(s / interval)
        seg_start = seg_i * interval
        seg_len = min(interval, total - seg_start)
        if seg_len < 1e-6:
            out.append(p.copy())
            continue
        t = (s - seg_start) / seg_len
        sag = droop * seg_len * 0.35 * math.sin(math.pi * min(1.0, max(0.0, t)))
        out.append(p + down * sag)
    return out


def resample_even(pts, step):
    """Evenly spaced samples including both endpoints.
    Returns (positions, tangents)."""
    acc = _cumlen(pts)
    total = acc[-1]
    n = max(2, int(round(total / max(step, 1e-5))) + 1)
    targets = [total * i / (n - 1) for i in range(n)]
    return _sample_at(pts, acc, targets)


def resample_spaced(pts, spacing):
    """Bulb positions: centered spacing along the strand.
    Returns (positions, tangents, u_norms)."""
    acc = _cumlen(pts)
    total = acc[-1]
    if total < spacing * 0.6:
        targets = [total * 0.5]
    else:
        count = int((total - spacing * 0.5) / spacing) + 1
        margin = (total - (count - 1) * spacing) * 0.5
        targets = [margin + i * spacing for i in range(count)]
    pos, tan = _sample_at(pts, acc, targets)
    u = [t / total if total > 0 else 0.0 for t in targets]
    return pos, tan, u


def _sample_at(pts, acc, targets):
    pos, tan = [], []
    j = 0
    for t in targets:
        t = min(max(t, 0.0), acc[-1])
        while j < len(acc) - 2 and acc[j + 1] < t:
            j += 1
        seg = acc[j + 1] - acc[j]
        f = 0.0 if seg < 1e-9 else (t - acc[j]) / seg
        pos.append(pts[j].lerp(pts[j + 1], f))
        d = pts[j + 1] - pts[j]
        tan.append(d.normalized() if d.length > 1e-9 else Vector((1, 0, 0)))
    return pos, tan


def transport_frames(points, tangents):
    """Parallel-transport normals along the polyline. Returns list[(t, n, b)]."""
    t0 = tangents[0]
    up = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    n = (up - t0 * up.dot(t0)).normalized()
    frames = []
    prev_t = t0
    for i, t in enumerate(tangents):
        if i > 0:
            axis = prev_t.cross(t)
            if axis.length > 1e-8:
                n = Quaternion(axis.normalized(), prev_t.angle(t)) @ n
            n = (n - t * n.dot(t))
            if n.length < 1e-8:
                up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
                n = up - t * up.dot(t)
            n = n.normalized()
        b = t.cross(n).normalized()
        frames.append((t.copy(), n.copy(), b.copy()))
        prev_t = t
    return frames


# ---------------------------------------------------------------- bulb templates

_template_cache = {}


def bulb_template(shape, sockets):
    """Return (verts:list[Vector], faces:list[tuple], uvs:list[list[(u,v)]]).
    Attach point at origin, bulb body below (-Z). Unit bulb radius = 1."""
    key = (shape, bool(sockets))
    if key in _template_cache:
        return _template_cache[key]

    bm = bmesh.new()
    if shape == 'OCTA':
        bmesh.ops.create_uvsphere(bm, u_segments=4, v_segments=2, radius=1.0)
    elif shape == 'GLOBE':
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    else:  # ROUND / TEARDROP
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)

    if shape == 'TEARDROP':
        for v in bm.verts:
            t = (v.co.z + 1.0) * 0.5  # 0 bottom .. 1 top
            f = 1.0 - 0.55 * (t ** 2.0)
            v.co.x *= f
            v.co.y *= f
            v.co.z *= 1.12
    # move bulb body below attach point
    drop = -1.35 if sockets else -1.02
    if shape == 'TEARDROP':
        drop = -1.45 if sockets else -1.14
    for v in bm.verts:
        v.co.z += drop

    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    verts = [v.co.copy() for v in bm.verts]
    bm.verts.index_update()
    faces = [tuple(l.vert.index for l in f.loops) for f in bm.faces]
    bm.free()

    smooth = [True] * len(faces)

    if sockets:
        base = len(verts)
        S = 4
        rt, rb, z0, z1 = 0.42, 0.60, 0.06, -0.52
        top = [Vector((rt * math.cos(a), rt * math.sin(a), z0))
               for a in (2 * math.pi * k / S for k in range(S))]
        bot = [Vector((rb * math.cos(a), rb * math.sin(a), z1))
               for a in (2 * math.pi * k / S for k in range(S))]
        verts.extend(top)
        verts.extend(bot)
        for k in range(S):
            k1 = (k + 1) % S
            # side quad, outward winding (verified: e1=down x e2=tangential -> outward)
            faces.append((base + k, base + S + k, base + S + k1, base + k1))
            smooth.append(False)
        faces.append(tuple(base + k for k in range(S)))               # top cap (+z)
        smooth.append(False)
        faces.append(tuple(base + S + k for k in reversed(range(S)))) # bottom cap (-z)
        smooth.append(False)

    # per-corner UVs from vertex position (spherical-ish, decorative)
    zs = [v.z for v in verts]
    zmin, zmax = min(zs), max(zs)
    zr = max(zmax - zmin, 1e-6)
    uvs = []
    for f in faces:
        fuv = []
        for vi in f:
            co = verts[vi]
            u = 0.5 + math.atan2(co.y, co.x) / (2 * math.pi)
            v = (co.z - zmin) / zr
            fuv.append((u, v))
        uvs.append(fuv)

    _template_cache[key] = (verts, faces, uvs, smooth)
    return _template_cache[key]


def _orient_quat(direction):
    """Quaternion rotating template -Z to `direction`."""
    return Vector((0, 0, -1)).rotation_difference(direction.normalized())


# ---------------------------------------------------------------- materials

def _srgb(c):
    return (c[0], c[1], c[2], 1.0)


def ensure_wire_material():
    mat = bpy.data.materials.get("FairyLights_Wire")
    if mat is None:
        mat = bpy.data.materials.new("FairyLights_Wire")
        mat.use_nodes = True
        bsdf = None
        for n in mat.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                bsdf = n
                break
        if bsdf:
            bsdf.inputs["Base Color"].default_value = WIRE_COLOR
            bsdf.inputs["Roughness"].default_value = 0.55
        mat.diffuse_color = WIRE_COLOR
    return mat


def ensure_glow_material(name, color, strength):
    """Create or refresh an emission material. Reuses existing material by name
    (so user tweaks survive), but keeps emission color/strength in sync when the
    default node layout is still present."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        out.location = (220, 0)
        em = nt.nodes.new("ShaderNodeEmission")
        em.location = (0, 0)
        nt.links.new(em.outputs[0], out.inputs[0])
    # sync emission values if an Emission node exists
    if mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == 'EMISSION':
                n.inputs[0].default_value = _srgb(color)
                n.inputs[1].default_value = strength
                break
    mat.diffuse_color = _srgb(color)
    return mat


# ---------------------------------------------------------------- build

def build_string(context, curve_ob):
    """(Re)build the fairy-light mesh for a curve object. Returns mesh object."""
    s = curve_ob.afl
    polylines = sample_curve_polylines(curve_ob)
    if not polylines:
        raise RuntimeError("Curve has no usable strokes (need at least 2 points)")

    # world 'down' in curve-local space
    inv = curve_ob.matrix_world.inverted().to_3x3()
    down = (inv @ Vector((0, 0, -1))).normalized()

    colors = s.colors()
    n_col = len(colors)
    S = int(s.wire_sides)
    wr = s.wire_radius
    rng = random.Random(s.seed)

    verts = []
    faces = []
    f_mat = []     # material index per face
    f_uv = []      # per-face list of corner uvs
    f_uv2 = []     # per-face list of corner twinkle uvs
    f_col = []     # per-face corner color
    f_smooth = []

    tmpl_v, tmpl_f, tmpl_uv, tmpl_smooth = bulb_template(s.bulb_shape, s.sockets)
    bulb_total = 0

    for pts, cyclic in polylines:
        dense = densify(pts, min(s.wire_step, 0.03))
        dense = apply_droop(dense, s.droop, s.droop_step, down)

        # ---- wire tube
        wpos, wtan = resample_even(dense, s.wire_step)
        frames = transport_frames(wpos, wtan)
        base = len(verts)
        circ = max(2.0 * math.pi * wr, 1e-6)
        for i, (p, (t, n, b)) in enumerate(zip(wpos, frames)):
            for k in range(S):
                a = 2 * math.pi * k / S
                verts.append(p + (n * math.cos(a) + b * math.sin(a)) * wr)
        acc_w = _cumlen(wpos)
        for i in range(len(wpos) - 1):
            r0 = base + i * S
            r1 = base + (i + 1) * S
            u0 = acc_w[i] / circ
            u1 = acc_w[i + 1] / circ
            for k in range(S):
                k1 = (k + 1) % S
                faces.append((r0 + k, r0 + k1, r1 + k1, r1 + k))
                f_mat.append(0)
                v0 = k / S
                v1 = (k + 1) / S
                f_uv.append([(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
                f_uv2.append([(0.0, 0.0)] * 4)
                f_col.append([WIRE_COLOR] * 4)
                f_smooth.append(False)
        # caps
        last = base + (len(wpos) - 1) * S
        faces.append(tuple(base + k for k in reversed(range(S))))
        faces.append(tuple(last + k for k in range(S)))
        for cap in range(2):
            f_mat.append(0)
            f_uv.append([(0.0, 0.0)] * S)
            f_uv2.append([(0.0, 0.0)] * S)
            f_col.append([WIRE_COLOR] * S)
            f_smooth.append(False)

        # ---- bulbs
        bpos, btan, bu = resample_spaced(dense, s.spacing)
        bframes = transport_frames(bpos, btan)
        for i, (p, (t, n, b), u) in enumerate(zip(bpos, bframes, bu)):
            if s.orientation == 'HANG':
                d = down.copy()
            elif s.orientation == 'RADIAL':
                a = i * GOLDEN + rng.uniform(-0.2, 0.2)
                d = (n * math.cos(a) + b * math.sin(a)).normalized()
            else:  # WILD
                q = Quaternion((n * math.cos(rng.uniform(0, 2 * math.pi))
                                + b * math.sin(rng.uniform(0, 2 * math.pi))).normalized(),
                               rng.uniform(0.0, 1.0))
                d = (q @ down).normalized()
            quat = _orient_quat(d)
            # jitter: random tilt + spin
            if s.jitter > 0:
                spin = Quaternion(d, rng.uniform(0, 2 * math.pi))
                perp = d.orthogonal().normalized()
                tilt_axis = Quaternion(d, rng.uniform(0, 2 * math.pi)) @ perp
                tilt = Quaternion(tilt_axis, rng.uniform(0, s.jitter))
                quat = tilt @ spin @ quat
            rand_v = rng.random()
            mat_i = 1 + (bulb_total % n_col if s.color_mode == 'MULTI' else 0)
            col = _srgb(colors[(mat_i - 1) % n_col])
            vbase = len(verts)
            sz = s.bulb_size
            for tv in tmpl_v:
                verts.append(p + (quat @ tv) * sz)
            for fi, tf in enumerate(tmpl_f):
                faces.append(tuple(vbase + vi for vi in tf))
                f_mat.append(mat_i)
                f_uv.append(tmpl_uv[fi])
                f_uv2.append([(u, rand_v)] * len(tf))
                f_col.append([col] * len(tf))
                f_smooth.append(tmpl_smooth[fi])
            bulb_total += 1

    # ---- mesh datablock
    mesh = bpy.data.meshes.new(curve_ob.name + "_FairyLights")
    mesh.from_pydata([v[:] for v in verts], [], faces)
    mesh.update()

    for i, poly in enumerate(mesh.polygons):
        poly.material_index = f_mat[i]
        poly.use_smooth = f_smooth[i]

    uv1 = mesh.uv_layers.new(name="UVMap")
    uv2 = mesh.uv_layers.new(name="TwinkleData")
    li = 0
    for i, poly in enumerate(mesh.polygons):
        for c in range(poly.loop_total):
            uv1.data[li].uv = f_uv[i][c]
            uv2.data[li].uv = f_uv2[i][c]
            li += 1

    try:
        vcol = mesh.color_attributes.new(name="BulbColor", type='BYTE_COLOR', domain='CORNER')
        li = 0
        for i, poly in enumerate(mesh.polygons):
            for c in range(poly.loop_total):
                vcol.data[li].color = f_col[i][c]
                li += 1
    except Exception:
        pass  # very old builds: skip vertex colors

    mesh.validate()

    # ---- materials
    mats = [ensure_wire_material()]
    if s.color_mode == 'SINGLE':
        mats.append(ensure_glow_material("FairyLights_Glow", colors[0], s.emission))
    else:
        for i, c in enumerate(colors):
            mats.append(ensure_glow_material("FairyLights_Glow_%d" % (i + 1), c, s.emission))
    for m in mats:
        mesh.materials.append(m)

    # ---- object management (replace previous generation)
    old = s.generated
    name = curve_ob.name + "_FairyLights"
    if old is not None and old.name in bpy.data.objects:
        old_mesh = old.data
        old.data = mesh
        old.name = name
        if old_mesh and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
        ob = old
    else:
        ob = bpy.data.objects.new(name, mesh)
        context.collection.objects.link(ob)
    ob.parent = curve_ob
    ob.matrix_parent_inverse.identity()
    ob.matrix_basis.identity()
    ob["afl_source"] = curve_ob.name
    ob["afl_version"] = "1.0.0"

    s.generated = ob
    s.is_string = True
    s.stat_bulbs = bulb_total
    tris = 0
    for poly in mesh.polygons:
        tris += max(poly.loop_total - 2, 1)
    s.stat_tris = tris
    return ob
