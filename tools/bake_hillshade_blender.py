#!/usr/bin/env python3
"""Offline hillshade and ambient occlusion baking tool using Blender CLI.
Usage:
    blender -b -P tools/bake_hillshade_blender.py
Outputs:
    docs/baked_hillshade.png (high-contrast terrain lighting for WebGL or SVG overlay)
"""
import os, sys, time, json

try:
    import bpy
except ImportError:
    print("This script must be run inside Blender CLI: blender -b -P tools/bake_hillshade_blender.py")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
json_path = os.path.join(ROOT, "docs", "anthousa_world3d.json")

if not os.path.exists(json_path):
    print(f"Error: {json_path} not found. Please run 'python engine/export_to_sim3d.py' first.")
    sys.exit(1)

print("=== Anthousa 3D: Baking Hillshade and Cavity Map ===")
t0 = time.time()

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x = 1024
scene.render.resolution_y = 640
scene.render.engine = 'BLENDER_WORKBENCH'

scene.display.shading.light = 'FLAT'
scene.display.shading.color_type = 'SINGLE'
scene.display.shading.single_color = (0.78, 0.74, 0.66)
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = 'BOTH'

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

g = data['grid']
nx, nz = g['nx'], g['nz']

mesh = bpy.data.meshes.new("RealTerrain")
obj = bpy.data.objects.new("RealTerrainObj", mesh)
scene.collection.objects.link(obj)

verts, faces = [], []
for j in range(nz):
    for i in range(nx):
        idx = j * nx + i
        x = g['x0'] + i * g['step']
        z = g['z0'] + j * g['step']
        is_water = g['water'][idx] == 1
        h = -2.0 if is_water else g['heights'][idx] * 0.28
        verts.append((x, z, h))

for j in range(nz - 1):
    for i in range(nx - 1):
        a = j * nx + i
        b = a + 1
        c = a + nx
        d = c + 1
        faces.append((a, b, d, c))

mesh.from_pydata(verts, [], faces)
mesh.update()

cam_data = bpy.data.cameras.new("BakeCam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = g['x1'] - g['x0']
cam_obj = bpy.data.objects.new("BakeCamObj", cam_data)
cam_obj.location = ((g['x0'] + g['x1'])/2, (g['z0'] + g['z1'])/2, 300)
cam_obj.rotation_euler = (0, 0, 0)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

out_path = os.path.join(ROOT, "docs", "baked_hillshade.png")
scene.render.filepath = out_path
bpy.ops.render.render(write_still=True)

print(f"Bake completed in {time.time()-t0:.2f}s -> {out_path}")
