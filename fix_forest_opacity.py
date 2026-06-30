"""
fix_forest_opacity.py
=====================
Fixes missing opacityThreshold on leaf/branch/grass shaders in
custom_forest_filled.usdc (and any other USD stage you point it at).

Usage (from the forest/ directory):
    python3 fix_forest_opacity.py
or:
    python3 fix_forest_opacity.py /path/to/custom_forest_filled.usdc

What it does
------------
Materials with an opacity input connected to a texture alpha channel need
an opacityThreshold so Isaac Sim / Storm renderer knows where to cut off
transparent pixels.  Without it the geometry renders as a glassy/blue blob.

Rules applied
-------------
  branch_hipoly_Mat_007   -> 78/255  = 0.306  (matches filename cutoff78)
  M_Branch_007*           -> 155/255 = 0.608  (matches filename cutoff155)
  M_Branch_009*           -> 160/255 = 0.627  (matches filename cutoff160)
  ST_Blades*              -> 0.5
  leaves                  -> 0.5

Already-correct shaders (M_Branch_001, M_Bark_001, branch_hipoly_Mat_001/002)
are detected automatically and left untouched.

Bark / ground / emissive materials have no opacity connection and are also
left alone.
"""

import sys
from pxr import Usd, UsdShade, Sdf

# --------------------------------------------------------------------------- #
USDC_PATH = 'corrected_forest.usdc'
if len(sys.argv) > 1:
    USDC_PATH = sys.argv[1]

# (pattern_in_material_path, threshold_value)
THRESHOLD_RULES = [
    ('branch_hipoly_Mat_007',  78  / 255),   # 0.306
    ('M_Branch_007',           155 / 255),   # 0.608
    ('M_Branch_009',           160 / 255),   # 0.627
    ('ST_Blades',              0.5),
    ('leaves',                 0.5),
]
# --------------------------------------------------------------------------- #


def get_threshold(mat_path: str):
    for pattern, val in THRESHOLD_RULES:
        if pattern in mat_path:
            return val
    return None


def main():
    print(f"Opening {USDC_PATH} ...")
    stage = Usd.Stage.Open(USDC_PATH)

    fixed               = []
    skipped_already_set = []
    no_opacity_conn     = []
    no_rule             = []

    for prim in stage.Traverse():
        if prim.GetTypeName() != 'Shader':
            continue
        attrs = {a.GetName(): a.Get() for a in prim.GetAttributes()}
        if attrs.get('info:id') != 'UsdPreviewSurface':
            continue

        shader   = UsdShade.Shader(prim)
        path_str = str(prim.GetPath())

        # ── Does this shader have opacity connected? ──────────────────────── #
        opacity_inp = shader.GetInput('opacity')
        if opacity_inp is None:
            no_opacity_conn.append(path_str)
            continue
        sources, _ = opacity_inp.GetConnectedSources()
        if not sources:
            no_opacity_conn.append(path_str)
            continue

        # ── Already has a threshold? ──────────────────────────────────────── #
        thresh_inp  = shader.GetInput('opacityThreshold')
        current_val = thresh_inp.Get() if thresh_inp is not None else None
        if current_val is not None:
            skipped_already_set.append((path_str, current_val))
            continue

        # ── Find the correct threshold for this material ──────────────────── #
        desired = get_threshold(path_str)
        if desired is None:
            no_rule.append(path_str)
            continue

        # ── Ensure the texture node exposes an 'a' (alpha) output ─────────── #
        src_info  = sources[0]
        tex_prim  = src_info.source.GetPrim()
        tex_shader = UsdShade.Shader(tex_prim)
        if tex_shader.GetOutput('a') is None:
            tex_shader.CreateOutput('a', Sdf.ValueTypeNames.Float)

        # ── Set the threshold ─────────────────────────────────────────────── #
        thresh = shader.CreateInput('opacityThreshold', Sdf.ValueTypeNames.Float)
        thresh.Set(float(desired))
        fixed.append((path_str, desired))

    stage.GetRootLayer().Save()

    # ── Report ────────────────────────────────────────────────────────────── #
    print(f"\n{'='*60}")
    print(f"FIXED  ({len(fixed)}):")
    for p, v in sorted(fixed):
        print(f"  {p:<60}  threshold = {v:.4f}")

    print(f"\nALREADY CORRECT  ({len(skipped_already_set)}):")
    for p, v in sorted(skipped_already_set):
        print(f"  {p:<60}  = {v}")

    if no_rule:
        print(f"\nWARNING — opacity connected but no rule matched  ({len(no_rule)}):")
        for p in sorted(no_rule):
            print(f"  {p}")

    print(f"\nNO OPACITY (bark/ground/emissive — untouched)  ({len(no_opacity_conn)}):")
    for p in sorted(no_opacity_conn):
        print(f"  {p}")

    print(f"\nSaved to {USDC_PATH}")


if __name__ == '__main__':
    main()
