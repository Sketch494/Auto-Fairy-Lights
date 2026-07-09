# Headless test suite for Auto Fairy Lights
# Run: blender -b --factory-startup -noaudio --python-exit-code 1 --python tests/test_addon.py
import math
import os
import sys
import traceback

import bpy
from mathutils import Vector

ADDON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "addon"))
sys.path.insert(0, ADDON_DIR)

PASS = []
FAIL = []


def check(name, cond, extra=""):
    if cond:
        PASS.append(name)
        print("  PASS  %s" % name)
    else:
        FAIL.append(name)
        print("  FAIL  %s  %s" % (name, extra))


def mesh_volume(mesh):
    """Signed volume — positive means consistently outward windings on closed islands."""
    vol = 0.0
    vs = mesh.vertices
    for poly in mesh.polygons:
        idx = poly.vertices
        v0 = vs[idx[0]].co
        for i in range(1, len(idx) - 1):
            v1 = vs[idx[i]].co
            v2 = vs[idx[i + 1]].co
            vol += v0.dot(v1.cross(v2)) / 6.0
    return vol


def make_swag_curve(name="Swag", z=2.0):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    sp = data.splines.new('BEZIER')
    sp.bezier_points.add(2)
    cos = [(-2, 0, z), (0, 0.4, z - 0.15), (2, 0, z)]
    for i, c in enumerate(cos):
        p = sp.bezier_points[i]
        p.co = Vector(c)
        p.handle_left_type = p.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(ob)
    return ob


def select_only(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


print("=" * 60)
print("Blender %s" % bpy.app.version_string)
print("=" * 60)

try:
    import auto_fairy_lights
    auto_fairy_lights.register()
    check("register", True)
except Exception:
    traceback.print_exc()
    check("register", False)
    raise SystemExit(1)

scene = bpy.context.scene
s = scene.afl

# ---------------------------------------------------------------- basic generate (MULTI)
s.color_mode = 'MULTI'
s.color_count = 4
s.spacing = 0.15
s.bulb_size = 0.02
s.bulb_shape = 'TEARDROP'
s.sockets = True
s.droop = 0.3

curve = make_swag_curve()
select_only(curve)
r = bpy.ops.afl.generate()
check("generate op", r == {'FINISHED'})

gen = curve.afl.generated
check("generated object", gen is not None and gen.name in bpy.data.objects)
mesh = gen.data
check("bulb count", curve.afl.stat_bulbs >= 20, "got %d" % curve.afl.stat_bulbs)
check("tri stat", curve.afl.stat_tris > 0)

mats = [m.name for m in mesh.materials]
check("wire mat slot0", mats and mats[0] == "FairyLights_Wire", str(mats))
check("multi glow mats", mats[1:] == ["FairyLights_Glow_%d" % i for i in range(1, 5)], str(mats))

used_mat_idx = {p.material_index for p in mesh.polygons}
check("all mat slots used", used_mat_idx == {0, 1, 2, 3, 4}, str(used_mat_idx))

check("uv1", "UVMap" in mesh.uv_layers)
check("uv2 twinkle", "TwinkleData" in mesh.uv_layers)

# twinkle data: glow faces carry (pos, rand); rand should be diverse, pos in [0,1]
uv2 = mesh.uv_layers["TwinkleData"]
rands = set()
pos_ok = True
li = 0
for poly in mesh.polygons:
    for _ in range(poly.loop_total):
        if poly.material_index >= 1:
            u, v = uv2.data[li].uv
            rands.add(round(v, 5))
            if not (-0.001 <= u <= 1.001):
                pos_ok = False
        li += 1
check("uv2 positions in 0..1", pos_ok)
check("uv2 randoms diverse", len(rands) >= curve.afl.stat_bulbs * 0.8,
      "%d distinct / %d bulbs" % (len(rands), curve.afl.stat_bulbs))

has_vcol = bool(getattr(mesh, "color_attributes", None)) and "BulbColor" in mesh.color_attributes
check("vertex colors", has_vcol)

vol = mesh_volume(mesh)
check("outward windings (volume > 0)", vol > 0, "vol=%.8f" % vol)

# droop sanity: wire should dip below the straight line between endpoints
zs = [v.co.z for v in mesh.vertices]
check("droop dips", min(zs) < 2.0 - 0.02, "minz=%.3f" % min(zs))

# emission mats wired up
m1 = bpy.data.materials["FairyLights_Glow_1"]
em = [n for n in m1.node_tree.nodes if n.type == 'EMISSION']
check("emission node", bool(em) and em[0].inputs[1].default_value > 0)

# ---------------------------------------------------------------- regenerate (settings change)
b0 = curve.afl.stat_bulbs
curve.afl.spacing = 0.08
select_only(curve)
r = bpy.ops.afl.regenerate()
check("regenerate op", r == {'FINISHED'})
check("regen changes bulbs", curve.afl.stat_bulbs > b0,
      "%d -> %d" % (b0, curve.afl.stat_bulbs))
check("regen no dup objects",
      sum(1 for o in bpy.data.objects if o.name.startswith(curve.name + "_FairyLights")) == 1)

# ---------------------------------------------------------------- SINGLE color mode
curve2 = make_swag_curve("Swag2", z=3.0)
s.color_mode = 'SINGLE'
select_only(curve2)
bpy.ops.afl.generate()
mats2 = [m.name for m in curve2.afl.generated.data.materials]
check("single glow mat", mats2 == ["FairyLights_Wire", "FairyLights_Glow"], str(mats2))

# ---------------------------------------------------------------- shapes & wire sides
for shape in ('OCTA', 'ROUND', 'GLOBE'):
    curve2.afl.bulb_shape = shape
    select_only(curve2)
    r = bpy.ops.afl.regenerate()
    check("shape %s" % shape, r == {'FINISHED'} and mesh_volume(curve2.afl.generated.data) > 0)
for sides in ('3', '6'):
    curve2.afl.wire_sides = sides
    select_only(curve2)
    r = bpy.ops.afl.regenerate()
    check("wire sides %s" % sides, r == {'FINISHED'})

# low-poly budget sanity: octa + no sockets should be tiny
curve2.afl.bulb_shape = 'OCTA'
curve2.afl.sockets = False
curve2.afl.wire_sides = '3'
curve2.afl.wire_step = 0.12
select_only(curve2)
bpy.ops.afl.regenerate()
per_bulb = curve2.afl.stat_tris / max(curve2.afl.stat_bulbs, 1)
check("ultra-low budget (<18 tris/bulb incl wire share)", per_bulb < 18,
      "%.1f tris/bulb" % per_bulb)

# ---------------------------------------------------------------- draw -> finish flow
r = bpy.ops.afl.draw_string()
check("draw op", r == {'FINISHED'})
drawn = bpy.context.object
check("draw creates string curve", drawn.type == 'CURVE' and drawn.afl.is_string)
# simulate a drawn stroke: add a spline programmatically
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
sp = drawn.data.splines.new('POLY')
sp.points.add(30)
for i in range(31):
    t = i / 30.0
    sp.points[i].co = (t * 4 - 2, math.sin(t * math.pi * 2) * 0.5, 1.5, 1.0)
bpy.ops.object.mode_set(mode='EDIT')
r = bpy.ops.afl.finish()
check("finish op", r == {'FINISHED'})
check("finish generated", drawn.afl.generated is not None)

# ---------------------------------------------------------------- orientations
for orient in ('RADIAL', 'WILD'):
    drawn.afl.orientation = orient
    select_only(drawn)
    r = bpy.ops.afl.regenerate()
    check("orientation %s" % orient, r == {'FINISHED'})

# ---------------------------------------------------------------- multi-spline in one curve
multi = make_swag_curve("Multi", z=4.0)
sp = multi.data.splines.new('POLY')
sp.points.add(10)
for i in range(11):
    sp.points[i].co = (i * 0.3 - 1.5, 1.0, 4.2, 1.0)
select_only(multi)
bpy.ops.afl.generate()
check("multi-spline", multi.afl.stat_bulbs > 25, "bulbs=%d" % multi.afl.stat_bulbs)

# ---------------------------------------------------------------- grease pencil
gp_tested = False
try:
    if bpy.app.version < (4, 3, 0):
        gpd = bpy.data.grease_pencils.new("GPTest")
        gpo = bpy.data.objects.new("GPTest", gpd)
        bpy.context.collection.objects.link(gpo)
        layer = gpd.layers.new("L")
        frame = layer.frames.new(1)
        stroke = frame.strokes.new()
        stroke.points.add(16)
        for i in range(16):
            stroke.points[i].co = (i * 0.2, 0.0, 1.0)
        gp_tested = True
    else:
        coll = getattr(bpy.data, "grease_pencils_v3", None) or bpy.data.grease_pencils
        gpd = coll.new("GPTest")
        gpo = bpy.data.objects.new("GPTest", gpd)
        bpy.context.collection.objects.link(gpo)
        layer = gpd.layers.new("L")
        frame = layer.frames.new(1)
        drawing = frame.drawing
        drawing.add_strokes([16])
        st = drawing.strokes[0]
        for i, p in enumerate(st.points):
            p.position = (i * 0.2, 0.0, 1.0)
        gp_tested = True
except Exception as e:
    print("  SKIP  grease pencil creation on this build: %r" % e)

if gp_tested:
    select_only(gpo)
    r = bpy.ops.afl.generate()
    ok = r == {'FINISHED'}
    made = [o for o in bpy.data.objects if o.name.startswith("GPTest_String")]
    check("grease pencil convert", ok and made and made[0].afl.stat_bulbs > 5,
          "bulbs=%s" % (made[0].afl.stat_bulbs if made else "-"))

# ---------------------------------------------------------------- export ready + FBX
select_only(drawn)
r = bpy.ops.afl.export_ready()
check("export ready op", r == {'FINISHED'})
gen = drawn.afl.generated
check("unparented", gen.parent is None)
check("identity transform", gen.matrix_world == gen.matrix_world.Identity(4))

fbx_path = "/tmp/afl_test.fbx"
try:
    select_only(gen)
    bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=True)
    ok = os.path.exists(fbx_path) and os.path.getsize(fbx_path) > 10000
    check("fbx export", ok, "size=%s" % (os.path.getsize(fbx_path) if os.path.exists(fbx_path) else 0))
except Exception as e:
    check("fbx export", False, repr(e))

# glTF too (some VRChat/game flows prefer it)
try:
    select_only(gen)
    bpy.ops.export_scene.gltf(filepath="/tmp/afl_test.glb", use_selection=True)
    check("glb export", os.path.getsize("/tmp/afl_test.glb") > 5000)
except Exception as e:
    print("  SKIP  glb export: %r" % e)

# ---------------------------------------------------------------- unregister clean
try:
    auto_fairy_lights.unregister()
    check("unregister", True)
except Exception:
    traceback.print_exc()
    check("unregister", False)

print("-" * 60)
print("RESULT: %d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", ", ".join(FAIL))
    raise SystemExit(1)
print("ALL GREEN")
