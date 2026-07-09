# ✨ Auto Fairy Lights

**Draw strings of low-poly, game-ready fairy lights on any surface in Blender.**

Sketch a line with Blender's Draw tool — right onto roofs, trees, fences, walls — and Auto Fairy Lights turns the stroke into a wire full of glowing bulbs. Built for game and VRChat workflows: tiny tri counts, clean material slots, and per-bulb shader data baked into UV2.

Part of the **Auto** family by [Sketch494](https://github.com/Sketch494) — see also [Auto Bake](https://autobake.sketch494.online) and [Auto Standee](https://standee.sketch494.online).

![Hero](docs/hero.jpg)

## Install

**Blender 4.2+ (extension):** drag `auto_fairy_lights-1.0.0-extension.zip` into Blender, or `Edit > Preferences > Get Extensions > Install from Disk`.

**Blender 3.6 – 4.1 (legacy add-on):** `Edit > Preferences > Add-ons > Install`, pick `auto_fairy_lights-1.0.0.zip`, enable **Auto Fairy Lights**.

Panel lives in the 3D Viewport sidebar (`N`) → **Fairy Lights** tab.

## Use

1. Click **✏ Draw Light String** — you're dropped into the curve Draw tool with surface snapping on.
2. Sketch your string. Multiple strokes are fine (each becomes its own strand in the same set).
3. Click **✓ Finish & Generate**. Done — wire + bulbs, ready to tweak.
4. Change spacing / size / shape / colors and hit **Regenerate** anytime. The drawn curve stays editable.
5. **Make Export Ready**, then export FBX (or glTF) for Unity / VRChat.

Also works on existing geometry: select any curve **or Grease Pencil object** and hit **Generate on Selected** (GPv2 and GPv3 both supported).

## Low poly by design

| Bulb shape | Tris per bulb |
|---|---|
| Octa | 8 |
| Round | 20 |
| Teardrop | 20 |
| Globe | 80 |

Optional sockets add 12 tris per bulb. Wire is a 3/4/6-sided tube with adjustable segment length. The panel shows a live **bulb + triangle count** so you always know your budget. A 10 m string of teardrops at default density lands around **2k tris**.

## Made for Unity / VRChat shaders

The glow is **its own material slot** — separate from the wire — so you can recolor it or swap in any shader without touching the rest:

- `FairyLights_Wire` — the cable
- `FairyLights_Glow` — single-color mode
- `FairyLights_Glow_1 … _6` — multi-color mode (one slot per color, alternating along the string)

Baked per-bulb data for custom shader effects:

- **UV2.x** — normalized position along the strand (0→1). Drive chase / marquee patterns.
- **UV2.y** — stable random per bulb. Drive twinkle / blink offsets.
- **Vertex color** (`BulbColor`) — the bulb's color. Run rainbow strings on a single material if you prefer.

Example twinkle in shader-speak: `emission *= 0.5 + 0.5 * sin(_Time.y * 4 + uv2.y * 6.2831)`

## Blender-side rendering

Bulbs use plain Emission materials — enable Bloom (Eevee) or a Glare node (Cycles compositor) and they light up beautifully. Every preview image in this repo was generated with the add-on and rendered in Cycles.

## Compatibility

Tested headless on **Blender 3.6.23, 4.2.22, and 5.1.2** — 40/40 automated checks green on each, including FBX/glTF export and Grease Pencil conversion (GPv2 + GPv3).

## License

MIT © Sketch494
