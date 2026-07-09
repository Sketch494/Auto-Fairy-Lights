# Auto Fairy Lights — draw strings of low-poly, game-ready fairy lights
# Part of the Auto* family (Auto Bake, Auto Standee) by Sketch494
bl_info = {
    "name": "Auto Fairy Lights",
    "author": "Sketch494",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "3D Viewport > Sidebar (N) > Fairy Lights",
    "description": "Draw strings of low-poly, game-ready fairy lights on any surface. "
                   "Separate glow materials + UV2 twinkle data for Unity/VRChat shaders",
    "doc_url": "https://fairylights.sketch494.online",
    "tracker_url": "https://github.com/Sketch494/auto-fairy-lights/issues",
    "category": "Add Curve",
}

from . import props, operators, ui

MODULES = (props, operators, ui)


def register():
    for m in MODULES:
        m.register()


def unregister():
    for m in reversed(MODULES):
        m.unregister()


if __name__ == "__main__":
    register()
