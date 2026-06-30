"""
find_corrupt_prims.py
======================
Very defensive scan that wraps EVERY operation in try/except so it can
survive and report prims/attributes that are structurally broken
(e.g. invalid/expired prims left behind by repeated edits, or composition
arcs pointing at paths that don't fully resolve).

Usage:
    python3 find_corrupt_prims.py custom_forest_filled_2.usdc
"""

import sys
from pxr import Usd, UsdShade, Sdf

USDC_PATH = sys.argv[1] if len(sys.argv) > 1 else 'custom_forest_filled_2.usdc'

print(f"Opening: {USDC_PATH}")
stage = Usd.Stage.Open(USDC_PATH)
print("Stage opened OK.\n")

bad_prims = []
bad_attrs = []

print("Pass 1: checking every prim's basic validity...")
for prim in stage.Traverse():
    try:
        _ = prim.GetPath()
        _ = prim.GetTypeName()
        _ = prim.IsValid()
        _ = prim.GetName()
    except Exception as e:
        bad_prims.append((str(prim), repr(e)))
        continue

print(f"  Pass 1 done. Bad prims so far: {len(bad_prims)}\n")

print("Pass 2: checking every Shader prim's attributes individually...")
for prim in stage.Traverse():
    try:
        tname = prim.GetTypeName()
    except Exception as e:
        bad_prims.append((str(prim.GetPath()) if prim else '<unknown>', repr(e)))
        continue

    if tname != 'Shader':
        continue

    ppath = str(prim.GetPath())

    try:
        attrs = prim.GetAttributes()
    except Exception as e:
        bad_prims.append((ppath, f"GetAttributes failed: {e!r}"))
        continue

    for a in attrs:
        try:
            aname = a.GetName()
        except Exception as e:
            bad_attrs.append((ppath, '<unknown attr name>', f"GetName failed: {e!r}"))
            continue
        try:
            _ = a.Get()
        except Exception as e:
            bad_attrs.append((ppath, aname, f"Get() failed: {e!r}"))
        try:
            if a.HasAuthoredConnections():
                _ = a.GetConnections()
        except Exception as e:
            bad_attrs.append((ppath, aname, f"GetConnections failed: {e!r}"))

print(f"  Pass 2 done.\n")

print("Pass 3: checking material binding relationships...")
for prim in stage.Traverse():
    try:
        rel = prim.GetRelationship('material:binding')
        if rel and rel.IsValid():
            try:
                targets = rel.GetTargets()
                for t in targets:
                    tp = stage.GetPrimAtPath(t)
                    if tp is None or not tp.IsValid():
                        bad_prims.append((str(prim.GetPath()), f"material:binding points to invalid prim: {t}"))
            except Exception as e:
                bad_prims.append((str(prim.GetPath()), f"GetTargets failed: {e!r}"))
    except Exception as e:
        bad_prims.append((str(prim.GetPath()) if prim else '<unknown>', f"GetRelationship failed: {e!r}"))

print(f"  Pass 3 done.\n")

print("="*80)
print(f"BAD PRIMS ({len(bad_prims)}):")
for p, err in bad_prims:
    print(f"  {p}\n    -> {err}")

print(f"\nBAD ATTRIBUTES ({len(bad_attrs)}):")
for p, a, err in bad_attrs:
    print(f"  {p}.{a}\n    -> {err}")

if not bad_prims and not bad_attrs:
    print("\nNo structural corruption found via standard traversal.")
    print("The earlier crash may be triggered only when accessing a SPECIFIC")
    print("input's connections via UsdShade.Input wrapper (not raw Usd API).")
    print("Re-run the next script (per-material targeted probe) to isolate it.")
