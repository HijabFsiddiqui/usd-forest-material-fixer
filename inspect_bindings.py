"""
inspect_bindings.py
====================
Lists every mesh/prim in the stage along with the material it's bound to,
plus that material's key shader inputs (metallic, roughness, normal).

This helps identify WHY a specific object renders wrong (e.g. looking like
crumpled foil instead of leaves/rock) — usually it's because:
  - wrong material bound to the mesh (e.g. a metal material accidentally
    bound to foliage geometry)
  - metallic input set too high / connected to the wrong texture channel
  - normal map inverted or pointing at the wrong texture

Usage:
    python3 inspect_bindings.py custom_forest_filled.usdc
    python3 inspect_bindings.py custom_forest_filled.usdc --filter Spruce_LOD0_009
"""

import sys
from pxr import Usd, UsdShade, UsdGeom

USDC_PATH = sys.argv[1] if len(sys.argv) > 1 else 'custom_forest_filled.usdc'
NAME_FILTER = None
if '--filter' in sys.argv:
    NAME_FILTER = sys.argv[sys.argv.index('--filter') + 1]

stage = Usd.Stage.Open(USDC_PATH)

def describe_shader(mat_prim):
    """Find the UsdPreviewSurface shader under a Material prim and dump key inputs."""
    shader_prim = None
    for child in Usd.PrimRange(mat_prim):
        if child.GetTypeName() == 'Shader':
            attrs = {a.GetName(): a.Get() for a in child.GetAttributes()}
            if attrs.get('info:id') == 'UsdPreviewSurface':
                shader_prim = child
                break
    if shader_prim is None:
        return "    <no UsdPreviewSurface found>"

    shader = UsdShade.Shader(shader_prim)
    lines = [f"    shader: {shader_prim.GetPath()}"]
    for name in ['diffuseColor', 'metallic', 'roughness', 'normal', 'opacity', 'opacityThreshold', 'emissiveColor']:
        inp = shader.GetInput(name)
        if inp is None:
            continue
        srcs, _ = inp.GetConnectedSources()
        if srcs:
            src = srcs[0]
            out_name = src.GetSourceName() if hasattr(src, 'GetSourceName') else getattr(src, 'sourceName', '?')
            lines.append(f"      {name}: CONNECTED <- {src.source.GetPath()}.{out_name}")
        else:
            val = inp.Get()
            if val is not None:
                lines.append(f"      {name}: {val}")
    return "\n".join(lines)

print(f"Opening: {USDC_PATH}\n")
print("="*80)

count = 0
for prim in stage.Traverse():
    if not prim.IsA(UsdGeom.Mesh) and not prim.IsA(UsdGeom.Xformable):
        continue
    if prim.GetTypeName() not in ('Mesh',):
        continue

    name = str(prim.GetPath())
    if NAME_FILTER and NAME_FILTER not in name:
        continue

    binding_api = UsdShade.MaterialBindingAPI(prim)
    rel = binding_api.GetDirectBindingRel()
    targets = rel.GetTargets()

    print(f"\nMESH: {name}")
    if not targets:
        print("    <no material bound>")
        continue

    for t in targets:
        mat_prim = stage.GetPrimAtPath(t)
        print(f"    bound material: {t}")
        if mat_prim:
            print(describe_shader(mat_prim))
        count += 1

print(f"\n{'='*80}")
print(f"Total bound meshes shown: {count}")
print("\nLook for:")
print("  - metallic value close to 1.0 on something that should be organic (leaves/bark)")
print("  - diffuseColor NOT connected (falls back to default grey, looks flat/metal under light)")
print("  - normal connected to the WRONG texture (e.g. a metallicRoughness map used as normal)")
