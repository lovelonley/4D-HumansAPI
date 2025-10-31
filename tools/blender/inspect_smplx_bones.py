import bpy

# Create a new scene with a SMPL-X character
try:
    bpy.ops.scene.smplx_add_gender()
except Exception as e:
    print('[ERR] add gender:', e)

arm = None
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        arm = obj
        break

if arm is None:
    print('[ERR] no armature found')
else:
    print('[ARM]', arm.name)
    for b in arm.data.bones:
        print('[BONE]', b.name)

print('[done]')



