import bpy

print("[addons]", list(bpy.context.preferences.addons.keys()))

ops = []
for cls in bpy.types.Operator.__subclasses__():
    try:
        op_id = getattr(cls, 'bl_idname', '')
        if op_id and ('smpl' in op_id.lower() or 'smplx' in op_id.lower()):
            ops.append(op_id)
    except Exception:
        pass

ops = sorted(set(ops))
for o in ops:
    print("[op]", o)

print("[done]")



