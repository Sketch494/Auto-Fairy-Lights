# Render preview shots of Auto Fairy Lights output (Cycles CPU, headless)
# blender -b --factory-startup -noaudio --python-exit-code 1 --python tests/render_preview.py -- <shot> <outpath>
import math
import os
import sys

import bpy
from mathutils import Vector

ADDON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "addon"))
sys.path.insert(0, ADDON_DIR)
import auto_fairy_lights
auto_fairy_lights.register()

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["hero", "/tmp/afl_hero.png"]
SHOT = argv[0]
OUT = argv[1]

C = bpy.context
scene = C.scene


# ------------------------------------------------------------ helpers
def mat_simple(name, color, rough=0.9, emit=None, emit_strength=1.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = [n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    if emit is not None:
        try:
            bsdf.inputs["Emission Color"].default_value = (*emit, 1)
            bsdf.inputs["Emission Strength"].default_value = emit_strength
        except KeyError:
            bsdf.inputs["Emission"].default_value = (*emit, 1)
            try:
                bsdf.inputs["Emission Strength"].default_value = emit_strength
            except KeyError:
                pass
    return m


def box(name, size, loc, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    ob = C.object
    ob.name = name
    ob.scale = size
    if mat:
        ob.data.materials.append(mat)
    return ob


def cone(name, r, h, loc, mat):
    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=r, depth=h, location=loc)
    ob = C.object
    ob.name = name
    if mat:
        ob.data.materials.append(mat)
    return ob


def bezier_swag(name, a, b, sag=0.0):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    sp = data.splines.new('BEZIER')
    sp.bezier_points.add(1)
    p0, p1 = sp.bezier_points[0], sp.bezier_points[1]
    p0.co, p1.co = Vector(a), Vector(b)
    for p in (p0, p1):
        p.handle_left_type = p.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, data)
    C.collection.objects.link(ob)
    return ob


def poly_curve(name, pts):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    sp = data.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1.0)
    ob = bpy.data.objects.new(name, data)
    C.collection.objects.link(ob)
    return ob


def gen(curve, **settings):
    for o in C.selected_objects:
        o.select_set(False)
    curve.select_set(True)
    C.view_layer.objects.active = curve
    from auto_fairy_lights.props import copy_settings
    copy_settings(scene.afl, curve.afl)
    curve.afl.is_string = True
    for k, v in settings.items():
        setattr(curve.afl, k, v)
    bpy.ops.afl.regenerate()
    return curve


# ------------------------------------------------------------ world & render setup
# purge factory-startup defaults (cube, light, camera)
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

scene.render.engine = 'CYCLES'
scene.cycles.samples = int(os.environ.get("AFL_SAMPLES", "80"))
scene.cycles.use_denoising = True
scene.render.resolution_x = int(os.environ.get("AFL_RESX", "1680"))
scene.render.resolution_y = int(os.environ.get("AFL_RESY", "945"))
scene.render.film_transparent = False
try:
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium High Contrast'
except Exception:
    pass

world = bpy.data.worlds.new("Night")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.0025, 0.004, 0.010, 1)
bg.inputs[1].default_value = 1.0

# dim blue moonlight
bpy.ops.object.light_add(type='SUN', location=(4, -6, 8))
moon = C.object
moon.data.energy = 0.35
moon.data.color = (0.55, 0.65, 1.0)
moon.rotation_euler = (math.radians(55), math.radians(-12), math.radians(35))

ground = box("Ground", (30, 30, 0.1), (0, 0, -0.05),
             mat_simple("GroundMat", (0.020, 0.028, 0.022)))

# glare compositor
scene.use_nodes = True
nt = scene.node_tree
nt.nodes.clear()
rl = nt.nodes.new("CompositorNodeRLayers")
glare = nt.nodes.new("CompositorNodeGlare")
glare.glare_type = 'FOG_GLOW'
glare.quality = 'HIGH'
glare.threshold = 1.0
glare.size = 8
comp = nt.nodes.new("CompositorNodeComposite")
nt.links.new(rl.outputs[0], glare.inputs[0])
nt.links.new(glare.outputs[0], comp.inputs[0])

wood = mat_simple("Wood", (0.045, 0.026, 0.015), 0.75)
dark = mat_simple("DarkWall", (0.022, 0.018, 0.015), 0.85)
warmwin = mat_simple("Window", (0.02, 0.01, 0.005), 0.4,
                     emit=(1.0, 0.45, 0.12), emit_strength=3.2)

# ------------------------------------------------------------ shots
if SHOT == "hero":
    # cabin face
    box("Cabin", (7.5, 0.4, 3.2), (0, 1.6, 1.6), dark)
    box("Roof", (8.2, 1.2, 0.18), (0, 1.25, 3.28), wood)
    box("Window1", (0.9, 0.06, 1.0), (-1.9, 1.38, 1.45), warmwin)
    box("Window2", (0.9, 0.06, 1.0), (1.9, 1.38, 1.45), warmwin)
    box("Door", (0.95, 0.08, 2.0), (0, 1.38, 1.0), wood)
    # porch posts + beam
    for x in (-2.9, 2.9):
        box("Post", (0.14, 0.14, 2.5), (x, -0.9, 1.25), wood)
    box("Beam", (6.1, 0.16, 0.14), (0, -0.9, 2.55), wood)

    scene.afl.emission = 30.0
    # double swag across the porch beam
    sw = poly_curve("SwagA", [(-2.9, -0.98, 2.5), (-1.45, -1.02, 2.5),
                              (0.0, -1.02, 2.5), (1.45, -1.02, 2.5), (2.9, -0.98, 2.5)])
    gen(sw, color_mode='SINGLE', bulb_shape='TEARDROP', spacing=0.14,
        bulb_size=0.021, droop=0.55, droop_step=1.5, sockets=True, seed=3)
    # roofline multicolor
    rf = poly_curve("Roofline", [(-4.0, 0.62, 3.35), (-2.0, 0.6, 3.37),
                                 (0.0, 0.6, 3.37), (2.0, 0.6, 3.37), (4.0, 0.62, 3.35)])
    gen(rf, color_mode='MULTI', color_count=4, bulb_shape='ROUND', spacing=0.17,
        bulb_size=0.022, droop=0.35, droop_step=1.35, seed=7)
    # tree beside porch with spiral string
    tree_x, tree_y = 3.9, -2.4
    cone("Tree1", 1.15, 1.7, (tree_x, tree_y, 0.85), mat_simple("Pine", (0.012, 0.030, 0.014)))
    cone("Tree2", 0.85, 1.4, (tree_x, tree_y, 1.75), bpy.data.materials["Pine"])
    cone("Tree3", 0.55, 1.1, (tree_x, tree_y, 2.55), bpy.data.materials["Pine"])
    helix = []
    for i in range(120):
        t = i / 119.0
        z = 0.25 + t * 2.75
        r = 1.18 * (1.0 - t * 0.82) + 0.05
        a = t * math.pi * 7.5
        helix.append((tree_x + r * math.cos(a), tree_y + r * math.sin(a), z))
    hx = poly_curve("TreeSpiral", helix)
    gen(hx, color_mode='MULTI', color_count=5, bulb_shape='TEARDROP', spacing=0.16,
        bulb_size=0.02, droop=0.0, orientation='RADIAL', seed=11)

    bpy.ops.object.camera_add(location=(-1.0, -8.0, 1.55),
                              rotation=(math.radians(86), 0, math.radians(-9)))
    scene.camera = C.object
    C.object.data.lens = 30

elif SHOT == "closeup":
    scene.afl.emission = 22.0
    sw = poly_curve("Close", [(-1.6, 0, 1.62), (-0.5, 0.12, 1.58), (0.6, 0.05, 1.62), (1.7, -0.1, 1.66)])
    gen(sw, color_mode='MULTI', color_count=5, bulb_shape='GLOBE', spacing=0.17,
        bulb_size=0.03, droop=0.5, droop_step=0.9, sockets=True, seed=5,
        wire_radius=0.0045)
    box("Backdrop", (8, 0.2, 5), (0, 1.8, 2.0), dark)
    bpy.ops.object.camera_add(location=(-0.2, -1.35, 1.42),
                              rotation=(math.radians(88), 0, math.radians(-6)))
    scene.camera = C.object
    cam = C.object.data
    cam.lens = 62
    cam.dof.use_dof = True
    cam.dof.focus_distance = 1.05
    cam.dof.aperture_fstop = 1.8

elif SHOT == "shapes":
    scene.afl.emission = 9.0
    box("Backdrop", (10, 0.2, 6), (0, 1.2, 2.5), dark)
    shapes = [('OCTA', 2.72), ('ROUND', 2.12), ('TEARDROP', 1.52), ('GLOBE', 0.95)]
    for shape, z in shapes:
        c = poly_curve("Line_" + shape, [(-2.1, 0, z), (-0.7, 0, z - 0.04), (0.7, 0, z - 0.04), (2.1, 0, z)])
        gen(c, color_mode='SINGLE', bulb_shape=shape, spacing=0.16,
            bulb_size=0.028 if shape != 'GLOBE' else 0.034,
            droop=0.4, droop_step=1.0, sockets=True, seed=2)
    bpy.ops.object.camera_add(location=(0, -4.4, 1.8), rotation=(math.radians(90), 0, 0))
    scene.camera = C.object
    C.object.data.lens = 40

scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("RENDER DONE:", OUT)
