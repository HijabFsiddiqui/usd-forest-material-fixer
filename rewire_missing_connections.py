"""
rewire_missing_connections.py
==============================
Fixes shaders where the texture nodes (Image_Texture) exist and have proper
outputs declared, but the Principled_BSDF / UsdPreviewSurface shader's
diffuseColor / opacity / normal inputs were never connected to them.

This is different from "dangling connection" corruption -- here the
connection was simply never authored at all, even though both endpoints
exist and are valid.

Usage:
    python3 rewire_missing_connections.py corrected_forest.usdc
    python3 rewire_missing_connections.py corrected_forest.usdc --apply
"""

import sys
from pxr import Usd, UsdShade, Sdf

USDC_PATH = sys.argv[1] if len(sys.argv) > 1 else 'corrected_forest.usdc'
APPLY = '--apply' in sys.argv

stage = Usd.Stage.Open(USDC_PATH)

print(f"Opening: {USDC_PATH}")
print(f"Mode: {'APPLY FIXES' if APPLY else 'DRY RUN (use --apply to fix)'}")
print("=" * 80)

FOLIAGE_NAME_HINTS = ['branch', 'leaf', 'leaves', 'blade', 'st_blades', 'needle']

def is_foliage_material(mat_path: str) -> bool:
    lname = mat_path.lower()
    return any(hint in lname for hint in FOLIAGE_NAME_HINTS)

fixed = []
skipped_already_connected = []
skipped_not_foliage = []

for prim in stage.Traverse():
    if prim.GetTypeName() != 'Shader':
        continue
    attrs = {a.GetName(): a.Get() for a in prim.GetAttributes()}
    if attrs.get('info:id') != 'UsdPreviewSurface':
        continue

    shader = UsdShade.Shader(prim)
    mat_path = str(prim.GetPath())
    mat_prim = prim.GetParent()  # the Material prim containing this shader

    is_foliage = is_foliage_material(mat_path)

    # Find texture children directly under the material
    base_tex = None     # color/alpha texture (first non-normal Image_Texture)
    normal_tex = None   # normal map texture

    for child in mat_prim.GetChildren():
        cattrs = {a.GetName(): a.Get() for a in child.GetAttributes()}
        if cattrs.get('info:id') != 'UsdUVTexture':
            continue
        fval = str(cattrs.get('inputs:file', '')).lower()
        if 'normal' in fval or '_n.' in fval or '_nrm' in fval:
            if normal_tex is None:
                normal_tex = child
        else:
            if base_tex is None:
                base_tex = child

    # ---- diffuseColor ----
    if base_tex is not None:
        diff_inp = shader.GetInput('diffuseColor')
        if diff_inp is None:
            diff_inp = shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f)
        already = False
        try:
            srcs, _ = diff_inp.GetConnectedSources()
            already = bool(srcs)
        except Exception:
            already = False  # treat unresolvable as "not connected", will fix

        if already:
            skipped_already_connected.append((mat_path, 'diffuseColor'))
        else:
            print(f"\n{mat_path}.diffuseColor -> NOT connected")
            print(f"  will connect to {base_tex.GetPath()}.rgb")
            if APPLY:
                tex_shader = UsdShade.Shader(base_tex)
                diff_inp.GetAttr().ClearConnections()
                diff_inp.ConnectToSource(tex_shader.ConnectableAPI(), 'rgb')
                fixed.append((mat_path, 'diffuseColor', str(base_tex.GetPath())))

    # ---- opacity ----
    # IMPORTANT: only connect opacity for foliage-type materials (branch,
    # leaf, blade). Bark, logs, stumps, and generic material0/1/2 should
    # remain fully opaque (static 1.0) -- connecting their alpha channel
    # could introduce unwanted transparency if that channel isn't pure white.
    if base_tex is not None and is_foliage:
        op_inp = shader.GetInput('opacity')
        if op_inp is None:
            op_inp = shader.CreateInput('opacity', Sdf.ValueTypeNames.Float)
        already = False
        try:
            srcs, _ = op_inp.GetConnectedSources()
            already = bool(srcs)
        except Exception:
            already = False

        if already:
            skipped_already_connected.append((mat_path, 'opacity'))
        else:
            print(f"\n{mat_path}.opacity -> NOT connected")
            print(f"  will connect to {base_tex.GetPath()}.a")
            if APPLY:
                tex_shader = UsdShade.Shader(base_tex)
                op_inp.GetAttr().ClearConnections()
                op_inp.ConnectToSource(tex_shader.ConnectableAPI(), 'a')
                fixed.append((mat_path, 'opacity', str(base_tex.GetPath())))

    elif base_tex is not None and not is_foliage:
        skipped_not_foliage.append((mat_path, 'opacity'))

    # ---- normal ----
    if normal_tex is not None:
        norm_inp = shader.GetInput('normal')
        if norm_inp is None:
            norm_inp = shader.CreateInput('normal', Sdf.ValueTypeNames.Normal3f)
        already = False
        try:
            srcs, _ = norm_inp.GetConnectedSources()
            already = bool(srcs)
        except Exception:
            already = False

        if already:
            skipped_already_connected.append((mat_path, 'normal'))
        else:
            print(f"\n{mat_path}.normal -> NOT connected")
            print(f"  will connect to {normal_tex.GetPath()}.rgb")
            if APPLY:
                tex_shader = UsdShade.Shader(normal_tex)
                norm_inp.GetAttr().ClearConnections()
                norm_inp.ConnectToSource(tex_shader.ConnectableAPI(), 'rgb')
                fixed.append((mat_path, 'normal', str(normal_tex.GetPath())))

if APPLY and fixed:
    stage.GetRootLayer().Save()
    print(f"\nSaved: {USDC_PATH}")

print("\n" + "=" * 80)
print(f"Already connected (skipped): {len(skipped_already_connected)}")
print(f"Non-foliage opacity left untouched (intentional): {len(skipped_not_foliage)}")
print(f"Missing connections found:   {len(fixed) if APPLY else 'see above (dry run)'}")
if fixed:
    print(f"\nFixed ({len(fixed)}):")
    for m, i, t in fixed:
        print(f"  {m}.{i} <- {t}")
if not APPLY:
    print("\nRe-run with --apply to write these fixes.")
