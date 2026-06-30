import bpy
op = bpy.ops.wm.usd_export
rna = op.get_rna_type()
print("="*80)
print("bpy.ops.wm.usd_export parameters for this Blender version:")
print("="*80)
for prop in rna.properties:
    if prop.identifier == 'rna_type':
        continue
    print(f"  {prop.identifier:35s} default={prop.default!r}")
