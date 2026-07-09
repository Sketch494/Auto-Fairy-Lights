# Auto Fairy Lights - operators
import bpy
from mathutils import Vector

from . import generator
from .props import copy_settings


# ---------------------------------------------------------------- helpers

def resolve_string_curve(ob):
    """Given any object, find the fairy-string source curve (or None)."""
    if ob is None:
        return None
    if ob.type == 'CURVE' and ob.afl.is_string:
        return ob
    if ob.type == 'CURVE':
        return ob  # any curve can become a string
    src = ob.get("afl_source")
    if src:
        cand = bpy.data.objects.get(src)
        if cand and cand.type == 'CURVE':
            return cand
    if ob.parent and ob.parent.type == 'CURVE' and ob.parent.afl.is_string:
        return ob.parent
    return None


def gp_polylines(ob):
    """Best-effort stroke extraction from Grease Pencil (v2 <=4.2, v3 4.3+).
    Returns list of point-lists in GP-local space."""
    lines = []
    data = ob.data
    if ob.type == 'GPENCIL':  # legacy GPv2
        for layer in data.layers:
            frame = layer.active_frame
            if frame is None and layer.frames:
                frame = layer.frames[0]
            if frame is None:
                continue
            for stroke in frame.strokes:
                pts = [Vector(p.co) for p in stroke.points]
                if len(pts) >= 2:
                    lines.append(pts)
    elif ob.type == 'GREASEPENCIL':  # GPv3
        for layer in data.layers:
            frame = getattr(layer, "current_frame", None)
            frame = frame() if callable(frame) else frame
            drawing = getattr(frame, "drawing", None) if frame else None
            if drawing is None:
                # fallback: walk frames
                frames = getattr(layer, "frames", None)
                if frames:
                    for fr in frames:
                        drawing = getattr(fr, "drawing", None)
                        if drawing:
                            break
            if drawing is None:
                continue
            strokes = getattr(drawing, "strokes", [])
            for stroke in strokes:
                pts = []
                for p in stroke.points:
                    co = getattr(p, "position", None) or getattr(p, "co", None)
                    if co is not None:
                        pts.append(Vector(co))
                if len(pts) >= 2:
                    lines.append(pts)
    return lines


def curve_from_polylines(context, lines, matrix, name="FairyLightString"):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    for pts in lines:
        sp = data.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p.x, p.y, p.z, 1.0)
    ob = bpy.data.objects.new(name, data)
    ob.matrix_world = matrix.copy()
    context.collection.objects.link(ob)
    return ob


def do_generate(context, curve_ob, from_scene_defaults):
    if from_scene_defaults or not curve_ob.afl.is_string:
        copy_settings(context.scene.afl, curve_ob.afl)
    return generator.build_string(context, curve_ob)


# ---------------------------------------------------------------- operators

class AFL_OT_draw_string(bpy.types.Operator):
    """Create a new light string and start drawing it with the Draw tool"""
    bl_idname = "afl.draw_string"
    bl_label = "Draw Light String"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        s = context.scene.afl
        data = bpy.data.curves.new("FairyLightString", 'CURVE')
        data.dimensions = '3D'
        data.resolution_u = 12
        ob = bpy.data.objects.new("FairyLightString", data)
        context.collection.objects.link(ob)
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        copy_settings(s, ob.afl)
        ob.afl.is_string = True

        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bpy.ops.wm.tool_set_by_id(name="builtin.draw")
        except Exception:
            self.report({'INFO'}, "Pick the Draw tool in the toolbar to sketch")
        try:
            ps = context.scene.tool_settings.curve_paint_settings
            ps.curve_type = 'BEZIER'
            ps.depth_mode = s.draw_depth
            ps.use_offset_absolute = True
            ps.surface_offset = max(s.wire_radius * 2.0, 0.005)
            ps.error_threshold = 8
        except Exception:
            pass
        self.report({'INFO'}, "Draw your string (multiple strokes OK), then click Finish")
        return {'FINISHED'}


class AFL_OT_finish(bpy.types.Operator):
    """Leave draw mode and generate the fairy lights"""
    bl_idname = "afl.finish"
    bl_label = "Finish & Generate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (context.mode == 'EDIT_CURVE' and ob is not None
                and ob.type == 'CURVE' and ob.afl.is_string)

    def execute(self, context):
        ob = context.object
        bpy.ops.object.mode_set(mode='OBJECT')
        if not ob.data.splines:
            self.report({'WARNING'}, "Nothing drawn yet — string kept empty")
            return {'CANCELLED'}
        try:
            gen = generator.build_string(context, ob)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, "Fairy lights: %d bulbs, %d tris"
                    % (ob.afl.stat_bulbs, ob.afl.stat_tris))
        return {'FINISHED'}


class AFL_OT_generate(bpy.types.Operator):
    """Generate fairy lights on the selected curve or Grease Pencil strokes"""
    bl_idname = "afl.generate"
    bl_label = "Generate on Selected"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.selected_objects

    def execute(self, context):
        done = 0
        for ob in list(context.selected_objects):
            if ob.type == 'CURVE':
                try:
                    do_generate(context, ob, from_scene_defaults=not ob.afl.is_string)
                    done += 1
                except RuntimeError as e:
                    self.report({'WARNING'}, "%s: %s" % (ob.name, e))
            elif ob.type in {'GPENCIL', 'GREASEPENCIL'}:
                lines = gp_polylines(ob)
                if not lines:
                    self.report({'WARNING'}, "%s: no Grease Pencil strokes found" % ob.name)
                    continue
                curve = curve_from_polylines(context, lines, ob.matrix_world,
                                             name=ob.name + "_String")
                try:
                    do_generate(context, curve, from_scene_defaults=True)
                    done += 1
                except RuntimeError as e:
                    self.report({'WARNING'}, "%s: %s" % (ob.name, e))
        if not done:
            self.report({'ERROR'}, "Select a curve or Grease Pencil object")
            return {'CANCELLED'}
        return {'FINISHED'}


class AFL_OT_regenerate(bpy.types.Operator):
    """Rebuild the active fairy-light string with the current settings"""
    bl_idname = "afl.regenerate"
    bl_label = "Regenerate"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return resolve_string_curve(context.object) is not None

    def execute(self, context):
        curve = resolve_string_curve(context.object)
        try:
            generator.build_string(context, curve)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class AFL_OT_export_ready(bpy.types.Operator):
    """Bake transforms into the mesh so it drops cleanly into Unity / VRChat.
Unparents from the curve, applies all transforms, hides the source curve"""
    bl_idname = "afl.export_ready"
    bl_label = "Make Export Ready"
    bl_options = {'REGISTER', 'UNDO'}

    hide_curve: bpy.props.BoolProperty(
        name="Hide Source Curve", default=True,
        description="Hide the drawing curve after baking (kept for re-edits)")

    @classmethod
    def poll(cls, context):
        return resolve_string_curve(context.object) is not None

    def execute(self, context):
        curve = resolve_string_curve(context.object)
        ob = curve.afl.generated
        if ob is None or ob.name not in bpy.data.objects:
            self.report({'ERROR'}, "Generate the string first")
            return {'CANCELLED'}
        mw = ob.matrix_world.copy()
        ob.parent = None
        ob.matrix_world = mw
        ob.data.transform(ob.matrix_world)
        ob.matrix_world.identity()
        if self.hide_curve:
            curve.hide_set(True)
            curve.hide_render = True
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({'INFO'},
                    "Export ready — FBX this object. Glow material(s) are separate slots; "
                    "UV2 = (string position, random) per bulb")
        return {'FINISHED'}


CLASSES = (
    AFL_OT_draw_string,
    AFL_OT_finish,
    AFL_OT_generate,
    AFL_OT_regenerate,
    AFL_OT_export_ready,
)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
