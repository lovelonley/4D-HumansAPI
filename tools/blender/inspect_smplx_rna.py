import bpy

ops = [
    'scene.smplx_add_gender',
    'object.smplx_add_animation',
    'object.smplx_write_pose',
    'object.smplx_load_pose',
    'object.smplx_export_fbx',
]

for op_id in ops:
    try:
        op = getattr(bpy.ops, op_id.split('.')[0])
        fn = getattr(op, op_id.split('.')[1])
        rna = fn.get_rna_type()
        print(f"[RNA] {op_id}")
        for prop in rna.properties:
            if prop.is_readonly or prop.identifier == 'rna_type':
                continue
            print(f" - {prop.identifier}: type={prop.type} default={prop.default}")
    except Exception as e:
        print(f"[RNA-ERR] {op_id}: {e}")

print('[done]')



