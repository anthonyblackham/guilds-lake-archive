r"""Render a survey sheet as shaded relief in Blender (Cycles), straight down, from relief_prep.py's inputs.

    "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b -P scripts/figures/relief_render.py -- <survey_id>
        [--vex 3] [--sun-alt 30] [--sun-az 315] [--width 3000] [--samples 96] [--mesh 1800] [--out PATH]

The sheet is a plane at true proportions with the scan as its surface; build/relief/<id>/height.png pushes up only
the surveyed ground (the rest is flat paper). A low sun from the sheet's upper left (--sun-az is measured clockwise
from the top of the sheet, so 315 = upper left) rakes across it and a faint sky fills the shadows; the orthographic
camera looks straight down. Colours are kept as printed (Standard view transform). Writes
topography/renders/<id>-relief.jpg unless --out is given.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parents[2]
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
sid = args[0]
opt = {"--vex": 3.0, "--sun-alt": 30.0, "--sun-az": 315.0, "--width": 3000, "--samples": 96, "--mesh": 1800,
       "--out": str(HERE / "topography" / "renders" / f"{sid}-relief.jpg")}
for i in range(1, len(args) - 1, 2):
    opt[args[i]] = type(opt[args[i]])(args[i + 1])
src = HERE / "build" / "relief" / sid
meta = json.loads((src / "relief.json").read_text())

# a clean scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
U = 1000.0                                                   # feet per Blender unit
Wp, Hp = meta["sheet_ft"][0] / U, meta["sheet_ft"][1] / U

# the sheet: a UV'd grid, displaced by the height map, scan as its colour
nx = int(opt["--mesh"])
ny = max(2, round(nx * Hp / Wp))
bpy.ops.mesh.primitive_grid_add(x_subdivisions=nx, y_subdivisions=ny, size=1, calc_uvs=True)
sheet = bpy.context.active_object
sheet.scale = (Wp, Hp, 1)
bpy.ops.object.transform_apply(scale=True)
hmap = bpy.data.images.load(str(src / "height.png"))
hmap.colorspace_settings.name = "Non-Color"
tex = bpy.data.textures.new("height", type="IMAGE")
tex.image = hmap
tex.extension = "EXTEND"
tex.use_interpolation = True
mod = sheet.modifiers.new("relief", "DISPLACE")
mod.texture = tex
mod.texture_coords = "UV"
mod.mid_level = 0.0
mod.direction = "Z"
mod.strength = opt["--vex"] * meta["relief_ft"] / U
bpy.ops.object.shade_smooth()

mat = bpy.data.materials.new("sheet")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
img = nt.nodes.new("ShaderNodeTexImage")
img.image = bpy.data.images.load(str(src / "texture.jpg"))
img.interpolation = "Cubic"
nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.9
for name in ("Specular IOR Level", "Specular"):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = 0.15
        break
sheet.data.materials.append(mat)

# light: a low sun from the sheet's upper left, soft-edged; a faint even sky for the shadows
alt, az = math.radians(opt["--sun-alt"]), math.radians(opt["--sun-az"])
toward = Vector((math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt)))   # to the sun (y = sheet top)
sun_data = bpy.data.lights.new("sun", type="SUN")
sun_data.energy = 3.6
sun_data.angle = math.radians(3.0)
sun = bpy.data.objects.new("sun", sun_data)
scene.collection.objects.link(sun)
sun.rotation_euler = toward.to_track_quat("Z", "Y").to_euler()        # the lamp shines down its -Z
world = bpy.data.worlds.new("sky")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.42
scene.world = world

# camera: orthographic, straight down, framing the sheet exactly
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = max(Wp, Hp)
cam_data.clip_end = 100
cam = bpy.data.objects.new("cam", cam_data)
cam.location = (0, 0, 20)
scene.collection.objects.link(cam)
scene.camera = cam
r = scene.render
r.resolution_x = int(opt["--width"])
r.resolution_y = round(int(opt["--width"]) * Hp / Wp)
r.resolution_percentage = 100
r.image_settings.file_format = "JPEG"
r.image_settings.quality = 90
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

# Cycles on the GPU when there is one
r.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
    try:
        prefs.compute_device_type = kind
        prefs.get_devices()
        gpus = [dv for dv in prefs.devices if dv.type != "CPU"]
        if gpus:
            for dv in prefs.devices:
                dv.use = dv.type != "CPU"
            scene.cycles.device = "GPU"
            break
    except Exception:
        continue
scene.cycles.samples = int(opt["--samples"])
scene.cycles.use_denoising = True

Path(opt["--out"]).parent.mkdir(parents=True, exist_ok=True)
r.filepath = opt["--out"]
bpy.ops.render.render(write_still=True)
print("RENDERED", opt["--out"], r.resolution_x, r.resolution_y, "vex", opt["--vex"], "device", scene.cycles.device)
