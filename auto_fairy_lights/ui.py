# Auto Fairy Lights - sidebar panel
import bpy

from .operators import resolve_string_curve


class AFL_PT_panel(bpy.types.Panel):
    bl_label = "Fairy Lights"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Fairy Lights"

    def draw(self, context):
        layout = self.layout
        curve = resolve_string_curve(context.object)
        drawing = (context.mode == 'EDIT_CURVE' and context.object is not None
                   and context.object.type == 'CURVE' and context.object.afl.is_string)
        # settings source: active string's, else scene defaults
        s = curve.afl if (curve is not None and curve.afl.is_string) else context.scene.afl

        if drawing:
            box = layout.box()
            box.label(text="Sketch on surfaces with LMB", icon='GREASEPENCIL')
            box.label(text="Multiple strokes = one string set")
            layout.operator("afl.finish", icon='CHECKMARK')
        else:
            col = layout.column(align=True)
            col.scale_y = 1.4
            col.operator("afl.draw_string", icon='GREASEPENCIL')
            row = layout.row(align=True)
            row.operator("afl.generate", icon='OUTLINER_OB_CURVE')
            layout.prop(s, "draw_depth", text="Draw On")

        layout.separator()

        box = layout.box()
        box.label(text="Bulbs", icon='LIGHT_POINT')
        box.prop(s, "spacing")
        box.prop(s, "bulb_size")
        box.prop(s, "bulb_shape", text="Shape")
        row = box.row()
        row.prop(s, "sockets")
        row.prop(s, "seed")
        box.prop(s, "orientation", text="Aim")
        box.prop(s, "jitter")

        box = layout.box()
        box.label(text="Wire", icon='CURVE_DATA')
        box.prop(s, "wire_radius")
        row = box.row()
        row.prop(s, "wire_sides", text="")
        row.prop(s, "wire_step")
        box.prop(s, "droop")
        box.prop(s, "droop_step")

        box = layout.box()
        box.label(text="Glow", icon='MATERIAL')
        row = box.row()
        row.prop(s, "color_mode", expand=True)
        if s.color_mode == 'SINGLE':
            box.prop(s, "color_1", text="Color")
        else:
            box.prop(s, "color_count")
            row = box.row(align=True)
            for i in range(s.color_count):
                row.prop(s, "color_%d" % (i + 1), text="")
        box.prop(s, "emission")

        if curve is not None and curve.afl.is_string and not drawing:
            layout.separator()
            col = layout.column(align=True)
            col.scale_y = 1.2
            col.operator("afl.regenerate", icon='FILE_REFRESH')

            st = curve.afl
            box = layout.box()
            box.label(text="Stats", icon='MESH_DATA')
            row = box.row()
            row.label(text="Bulbs: %d" % st.stat_bulbs)
            row.label(text="Tris: %s" % "{:,}".format(st.stat_tris))

            box = layout.box()
            box.label(text="Game Export", icon='EXPORT')
            box.operator("afl.export_ready", icon='CHECKMARK')
            col = box.column(align=True)
            col.scale_y = 0.8
            col.label(text="Glow = own material slot(s)")
            col.label(text="UV2.x = position, UV2.y = random")
            col.label(text="Vertex color = bulb color")


def register():
    bpy.utils.register_class(AFL_PT_panel)


def unregister():
    bpy.utils.unregister_class(AFL_PT_panel)
