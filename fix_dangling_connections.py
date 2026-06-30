"""
fix_dangling_connections.py
============================
Finds shader inputs whose connections point at prims that no longer exist
in the stage (a common corruption after repeated edits/saves), and either
reports them or repairs them by reconnecting to the correct texture node
found elsewhere in the same material scope.

This specifically targets the crash we hit:
  UsdExpiredPrimAccessError on /root/_materials/leaves/Principled_BSDF

Usage:
    python3 fix_dangling_connections.py custom_forest_filled_2.usdc
    python3 fix_dangling_connections.py custom_forest_filled_2.usdc --apply
"""

import sys
from pxr import Usd, UsdShade, Sdf

USDC_PATH = sys.argv[1] if len(sys.argv) > 1 else 'custom_forest_filled_2.usdc'
APPLY = '--apply' in sys.argv

stage = Usd.Stage.Open(USDC_PATH)

print(f"Opening: {USDC_PATH}")
print(f"Mode: {'APPLY FIXES' if APPLY else 'DRY RUN (use --apply to fix)'}")
print("="*80)

# Collect all texture nodes globally, keyed by material scope
all_tex_by_scope = {}
for prim in stage.Traverse():
    if prim.GetTypeName() != 'Shader':
        continue
    attrs = {a.GetName(): a.Get() for a in prim.GetAttributes()}
    if 'inputs:file' in attrs:
        scope = str(prim.GetPath().GetParentPath())
        all_tex_by_scope.setdefault(scope, []).append((prim, str(attrs.get('inputs:file', ''))))

broken = []
fixed  = []

for prim in stage.Traverse():
    if prim.GetTypeName() != 'Shader':
        continue
    attrs = {a.GetName(): a.Get() for a in prim.GetAttributes()}
    if attrs.get('info:id') != 'UsdPreviewSurface':
        continue

    shader = UsdShade.Shader(prim)
    mat_path = str(prim.GetPath())
    scope = str(prim.GetPath().GetParentPath())

    for inp_name in ['diffuseColor', 'normal', 'opacity', 'metallic', 'roughness', 'emissiveColor']:
        inp = shader.GetInput(inp_name)
        if inp is None:
            continue

        attr = inp.GetAttr()

        # Skip phantom inputs: GetInput() can return a wrapper for an
        # attribute that was never actually authored on this prim. Trying
        # to read/clear/connect such an attribute throws
        # UsdExpiredPrimAccessError. A real authored attribute will always
        # report IsValid() True and HasValue/HasAuthoredConnections without
        # throwing.
        try:
            if not attr.IsValid():
                continue
        except Exception:
            continue

        # First try the raw Usd API (path-only, doesn't dereference prims)
        try:
            if not attr.HasAuthoredConnections():
                continue
            conn_paths = attr.GetConnections()
        except Exception as e:
            print(f"\nBROKEN (raw API): {mat_path}.{inp_name} -> {e!r}")
            conn_paths = []

        # Now try the UsdShade wrapper -- this is what actually throws
        # UsdExpiredPrimAccessError on truly dangling connections
        shade_broken = False
        try:
            srcs, _ = inp.GetConnectedSources()
        except Exception:
            shade_broken = True

        if not conn_paths and not shade_broken:
            continue

        # Build the list of "problem targets" to report/fix.
        # Case A: raw API gave us paths -> check each one for validity.
        # Case B: raw API gave nothing but UsdShade detected expiry ->
        #         we don't know the exact dangling path, but we still need
        #         to clear + reconnect this input.
        problem_targets = []
        for cp in conn_paths:
            target_prim_path = cp.GetPrimPath()
            target_prim = stage.GetPrimAtPath(target_prim_path)
            if not target_prim or not target_prim.IsValid():
                problem_targets.append(str(cp))

        if shade_broken and not problem_targets:
            problem_targets.append("<unresolvable via UsdShade, no raw path available>")

        for target_desc in problem_targets:
            broken.append((mat_path, inp_name, target_desc))
            print(f"\nBROKEN: {mat_path}.{inp_name}")
            print(f"  dangling target: {target_desc}")

            if APPLY:
                # Try to find a replacement texture in the same scope
                candidates = all_tex_by_scope.get(scope, [])
                replacement = None

                # Heuristic matching by input type
                for tprim, fval in candidates:
                    fval_lower = fval.lower()
                    if inp_name == 'normal' and ('normal' in fval_lower or '_n.' in fval_lower):
                        replacement = tprim
                        break
                    elif inp_name in ('diffuseColor', 'opacity') and (
                        'normal' not in fval_lower and '_n.' not in fval_lower
                    ):
                        replacement = tprim
                        break

                if replacement is None and candidates:
                    replacement = candidates[0][0]  # fallback: first texture in scope

                # Always clear first -- this removes the dangling connection
                # spec entirely, which is what stops UsdShade from throwing.
                try:
                    attr.ClearConnections()
                except Exception as e:
                    print(f"  WARNING: ClearConnections also failed: {e!r}")

                if replacement is not None:
                    tex_shader = UsdShade.Shader(replacement)
                    out_name = 'a' if inp_name == 'opacity' else 'rgb'
                    if tex_shader.GetOutput(out_name) is None:
                        type_map = {'a': Sdf.ValueTypeNames.Float, 'rgb': Sdf.ValueTypeNames.Float3}
                        tex_shader.CreateOutput(out_name, type_map[out_name])

                    inp.ConnectToSource(tex_shader.ConnectableAPI(), out_name)
                    fixed.append((mat_path, inp_name, str(replacement.GetPath())))
                    print(f"  FIXED -> reconnected to {replacement.GetPath()}.{out_name}")
                else:
                    print(f"  No replacement texture found in scope; cleared dangling connection only.")
                    fixed.append((mat_path, inp_name, "<cleared, no replacement>"))

if APPLY and (fixed or broken):
    stage.GetRootLayer().Save()
    print(f"\nSaved: {USDC_PATH}")

print("\n" + "="*80)
print(f"Broken connections found: {len(broken)}")
if fixed:
    print(f"Fixed: {len(fixed)}")
if not APPLY and broken:
    print("\nRe-run with --apply to fix these.")
