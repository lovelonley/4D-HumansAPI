#!/usr/bin/env python3
"""
Apply converted rotations and save .blend file for manual inspection.
"""

import sys
import numpy as np
import argparse

def parse_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--out", required=True)
    return ap.parse_args(argv)


def main():
    import bpy
    from mathutils import Matrix
    
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    args = parse_args(argv)
    
    # Load NPZ
    data = np.load(args.npz)
    R_root = data['R_root']
    
    # Clean scene
    for obj in list(bpy.data.objects):
        obj.select_set(True)
    if bpy.data.objects:
        bpy.ops.object.delete()
    
    # Create SMPL-X
    bpy.context.window_manager.smplx_tool.smplx_gender = 'female'
    bpy.ops.scene.smplx_add_gender()
    
    arm = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm = obj
        elif obj.type == 'MESH':
            bpy.data.objects.remove(obj, do_unlink=True)
    
    # Apply NPZ rotation DIRECTLY (no conversion)
    Mr = R_root[0]
    
    m = Matrix(((float(Mr[0,0]), float(Mr[0,1]), float(Mr[0,2])),
                (float(Mr[1,0]), float(Mr[1,1]), float(Mr[1,2])),
                (float(Mr[2,0]), float(Mr[2,1]), float(Mr[2,2]))))
    q = m.to_quaternion()
    
    bpy.context.scene.frame_set(1)
    pb = arm.pose.bones['pelvis']
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = q
    bpy.context.view_layer.update()
    
    print(f"\n[Test 1] Applied NPZ rotation directly (no conversion)")
    print(f"  Result: Character should be INVERTED")
    
    # Now add 180° X-axis rotation to armature object (like PHALP does to mesh)
    import math
    arm.rotation_mode = 'XYZ'
    arm.rotation_euler = (math.radians(180), 0, 0)
    bpy.context.view_layer.update()
    
    print(f"\n[Test 2] Added 180° X-axis rotation to armature object")
    print(f"  Result: Character should now be UPRIGHT")
    print(f"  Open {args.out} in Blender GUI to verify")
    
    # Save
    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    print(f"✓ Saved: {args.out}\n")


if __name__ == '__main__':
    main()

