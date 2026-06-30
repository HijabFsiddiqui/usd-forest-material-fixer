# usd-forest-material-fixer

A set of diagnostic and repair scripts for USD (`.usdc`/`.usd`) scenes where
`UsdPreviewSurface` materials have broken, missing, or misconfigured shader
connections occured after repeated Blender/glTF/FBX import-export
round trips (e.g. Sketchfab assets pulled into Blender, then exported to USD
for Isaac Sim / Omniverse).

Typical symptoms these scripts address:

- Leaves, branches, or grass rendering as solid/metallic instead of
  transparent cutout foliage
- Foliage looking "sparse" or patchy, with chunks of geometry missing
- Materials falling back to default grey/white shading instead of their
  intended texture
- Scripts crashing with `UsdExpiredPrimAccessError` when inspecting shader
  inputs


## Scripts, in recommended order

Run these against your file in this order. Each one that supports it has a
dry-run mode (no flags) and an apply mode (`--apply`) — **always run the dry
run first and read the output before applying.**

### 1. `find_corrupt_prims.py`

Defensively walks every prim and attribute in the stage, wrapped in
try/except, to confirm the file opens and traverses without structural
errors before you touch anything.

```bash
python3 find_corrupt_prims.py your_file.usdc
```

### 2. `fix_dangling_connections.py`

Finds shader inputs whose connections point at prims that no longer exist
(genuine corruption), while correctly skipping "phantom" inputs that were
never authored in the first place (a common false positive when probing
shader inputs by name).

```bash
python3 fix_dangling_connections.py your_file.usdc          # dry run
python3 fix_dangling_connections.py your_file.usdc --apply  # writes fixes
```

### 3. `rewire_missing_connections.py`

Reconnects `diffuseColor`, `opacity`, and `normal` to their sibling texture
nodes when the texture exists but the wire was never (re-)established.
Restricts `opacity` reconnection to foliage-pattern materials (branch, leaf,
blade) so opaque bark/log/stump materials aren't accidentally made
transparent.

```bash
python3 rewire_missing_connections.py your_file.usdc          # dry run
python3 rewire_missing_connections.py your_file.usdc --apply  # writes fixes
```

### 4. `fix_forest_opacity.py`

Sets `opacityThreshold` on foliage materials based on the cutoff value
encoded in each texture's filename (e.g. `_cutoff155.png` → threshold
155/255). Without this, alpha-cutout edges render inconsistently. Edit the
`USDC_PATH`/rule table at the top of the script to match your material
naming, or pass the path as an argument if your copy supports it.

```bash
python3 fix_forest_opacity.py your_file.usdc
```

### 5. `inspect_bindings.py`

Diagnostic tool: lists mesh prims, their bound material, and that
material's key shader inputs (diffuseColor, normal, opacity,
opacityThreshold, metallic, roughness). Use `--filter` to scope to a
specific material or mesh name.

```bash
python3 inspect_bindings.py your_file.usdc --filter M_Branch_009
```

## Recommended workflow

1. `find_corrupt_prims.py` — confirm the file is structurally sound
2. `fix_dangling_connections.py` (dry run, then `--apply`) — repair broken
   wires
3. `rewire_missing_connections.py` (dry run, then `--apply`) — restore
   missing wires
4. `fix_forest_opacity.py` — set correct alpha cutoffs
5. `inspect_bindings.py --filter <name>` — spot-check anything still
   suspicious
6. Reload the file in your DCC/viewer (Isaac Sim, Omniverse, Blender) —
   most tools cache the stage in memory and won't reflect changes until
   you close and reopen it
