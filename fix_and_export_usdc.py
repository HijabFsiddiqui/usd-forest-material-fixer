"""
fix_and_export_usdc.py
=======================
Run this via Blender's background Python, NOT by double-clicking.
It opens the .blend, fixes alpha-blend materials so transparency exports
correctly, then exports the scene directly to .usdc using Blender's native
USD exporter (bpy.ops.wm.usd_export) -- NOT the glTF exporter, which cannot
produce .usdc at all.
"""

import bpy
import os

# ---------------------------------------------------------------------------
# 1. Unpack all textures so the exporter can find real files on disk
# ---------------------------------------------------------------------------
bpy.ops.file.unpack_all(method='USE_ORIGINAL')

# ---------------------------------------------------------------------------
# 2. Fix alpha-blended materials so cutout transparency exports correctly
#    IMPORTANT: only touch materials that are actually meant to be cutout
#    (leaves/branches/grass blades). Bark, logs, stumps, and generic
#    material0/1/2 should stay fully opaque.
# ---------------------------------------------------------------------------
CUTOUT_NAME_HINTS = ['branch', 'leaf', 'leaves', 'blade', 'st_blades', 'needle']

def should_have_cutout(mat_name: str) -> bool:
    lname = mat_name.lower()
    return any(hint in lname for hint in CUTOUT_NAME_HINTS)

fixed_count = 0
for mat in bpy.data.materials:
    if not mat.use_nodes or mat.node_tree is None:
        continue
    if not should_have_cutout(mat.name):
        continue

    principled = next(
        (n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'),
        None
    )
    if principled is None:
        continue

    if mat.blend_method in ('HASHED', 'BLEND', 'CLIP'):
        mat.blend_method = 'CLIP'

        if hasattr(mat, 'alpha_threshold'):
            mat.alpha_threshold = 0.5

        tex_node = next(
            (n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE'),
            None
        )
        alpha_input = principled.inputs.get('Alpha')

        if tex_node is not None and alpha_input is not None and not alpha_input.links:
            mat.node_tree.links.new(tex_node.outputs['Alpha'], alpha_input)
            fixed_count += 1
            print(f"Fixed alpha link: {mat.name}")

print(f"Total materials fixed: {fixed_count}")

# ---------------------------------------------------------------------------
# 3. Export directly to USDC using Blender's native USD exporter
#    (the glTF exporter CANNOT write .usdc -- this is the correct operator)
# ---------------------------------------------------------------------------
output_path = os.path.expanduser(
    '~/Downloads/isaacsim/selfcreatedforest/forest/small_forest_filled.usdc'
)

bpy.ops.wm.usd_export(
    filepath=output_path,
    export_uvmaps=True,
    export_normals=True,
    export_materials=True,
    export_animation=False,
    selected_objects_only=False,
    export_textures_mode='NEW',
    overwrite_textures=True,
    relative_paths=True,
    generate_preview_surface=True,
    export_meshes=True,
    export_lights=True,
    export_cameras=True,
)

print(f"EXPORTED SUCCESSFULLY -> {output_path}")
