# Auto Fairy Lights - settings
import bpy
from bpy.props import (
    BoolProperty, FloatProperty, IntProperty, EnumProperty,
    FloatVectorProperty, PointerProperty,
)

BULB_SHAPES = [
    ('OCTA', "Octa (8 tris)", "Ultra low-poly octahedron bulb — for huge strings / quest maps"),
    ('ROUND', "Round (20 tris)", "Icosahedron mini-globe bulb"),
    ('TEARDROP', "Teardrop (20 tris)", "Classic pointed fairy bulb"),
    ('GLOBE', "Globe (80 tris)", "Big C9-style bulb for hero shots"),
]

ORIENTATIONS = [
    ('HANG', "Hang Down", "Bulbs hang toward world down with a little jitter (classic)"),
    ('RADIAL', "Radial", "Bulbs spiral around the wire (bottle-brush / garland look)"),
    ('WILD', "Wild", "Bulbs point in random downward-ish directions"),
]

WIRE_SIDES = [
    ('3', "Tri (3)", "3-sided wire — cheapest"),
    ('4', "Quad (4)", "4-sided wire"),
    ('6', "Hex (6)", "6-sided wire — roundest"),
]

COLOR_MODES = [
    ('SINGLE', "Single", "One glow material for every bulb"),
    ('MULTI', "Multi", "Alternating colors — one glow material per color"),
]

DRAW_DEPTH = [
    ('SURFACE', "On Surfaces", "Project the stroke onto geometry under the cursor (roofs, trees, walls)"),
    ('CURSOR', "Cursor Plane", "Draw on a plane through the 3D cursor"),
]

# properties copied scene-defaults -> string object (order irrelevant)
COPY_PROPS = (
    "spacing", "bulb_size", "bulb_shape", "sockets",
    "orientation", "jitter", "seed",
    "wire_radius", "wire_sides", "wire_step",
    "droop", "droop_step",
    "color_mode", "color_count",
    "color_1", "color_2", "color_3", "color_4", "color_5", "color_6",
    "emission", "draw_depth",
)


def _color(name, default):
    return FloatVectorProperty(
        name=name, subtype='COLOR', size=4, min=0.0, max=1.0,
        default=default,
    )


class AFLSettings(bpy.types.PropertyGroup):
    # internal
    is_string: BoolProperty(default=False, options={'HIDDEN'})
    generated: PointerProperty(type=bpy.types.Object)
    stat_bulbs: IntProperty(default=0, options={'HIDDEN'})
    stat_tris: IntProperty(default=0, options={'HIDDEN'})

    # string
    spacing: FloatProperty(
        name="Bulb Spacing", description="Distance between bulbs along the wire",
        default=0.15, min=0.02, max=10.0, subtype='DISTANCE')
    bulb_size: FloatProperty(
        name="Bulb Size", description="Bulb radius",
        default=0.02, min=0.001, max=2.0, subtype='DISTANCE')
    bulb_shape: EnumProperty(name="Bulb Shape", items=BULB_SHAPES, default='TEARDROP')
    sockets: BoolProperty(
        name="Sockets", description="Little plastic socket where each bulb meets the wire (+12 tris per bulb)",
        default=True)
    orientation: EnumProperty(name="Orientation", items=ORIENTATIONS, default='HANG')
    jitter: FloatProperty(
        name="Jitter", description="Random tilt applied to every bulb",
        default=0.24, min=0.0, max=1.2, subtype='ANGLE')
    seed: IntProperty(name="Seed", default=0, description="Randomize jitter / twinkle data")

    # wire
    wire_radius: FloatProperty(
        name="Wire Radius", default=0.004, min=0.0005, max=0.2, subtype='DISTANCE')
    wire_sides: EnumProperty(name="Wire Sides", items=WIRE_SIDES, default='4')
    wire_step: FloatProperty(
        name="Wire Segment", description="Length of each wire segment — bigger = fewer polys",
        default=0.06, min=0.01, max=2.0, subtype='DISTANCE')
    droop: FloatProperty(
        name="Droop", description="Sag the wire between anchor points for a natural hung look",
        default=0.25, min=0.0, max=1.0, subtype='FACTOR')
    droop_step: FloatProperty(
        name="Droop Interval", description="Distance between droop anchor points",
        default=0.7, min=0.1, max=10.0, subtype='DISTANCE')

    # colors
    color_mode: EnumProperty(name="Color Mode", items=COLOR_MODES, default='SINGLE')
    color_count: IntProperty(name="Colors", default=4, min=2, max=6)
    color_1: _color("Color 1", (1.00, 0.72, 0.35, 1.0))   # warm white
    color_2: _color("Color 2", (1.00, 0.05, 0.05, 1.0))   # red
    color_3: _color("Color 3", (0.08, 0.85, 0.15, 1.0))   # green
    color_4: _color("Color 4", (0.10, 0.35, 1.00, 1.0))   # blue
    color_5: _color("Color 5", (1.00, 0.55, 0.05, 1.0))   # gold
    color_6: _color("Color 6", (0.95, 0.10, 0.70, 1.0))   # magenta
    emission: FloatProperty(
        name="Glow Strength", description="Emission strength of the bulb material",
        default=6.0, min=0.0, max=1000.0)

    # draw tool
    draw_depth: EnumProperty(name="Draw On", items=DRAW_DEPTH, default='SURFACE')

    def colors(self):
        if self.color_mode == 'SINGLE':
            return [tuple(self.color_1)]
        return [tuple(getattr(self, "color_%d" % (i + 1))) for i in range(self.color_count)]


def copy_settings(src, dst):
    for p in COPY_PROPS:
        try:
            setattr(dst, p, getattr(src, p))
        except Exception:
            pass


def register():
    bpy.utils.register_class(AFLSettings)
    bpy.types.Scene.afl = PointerProperty(type=AFLSettings)
    bpy.types.Object.afl = PointerProperty(type=AFLSettings)


def unregister():
    del bpy.types.Object.afl
    del bpy.types.Scene.afl
    bpy.utils.unregister_class(AFLSettings)
