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
    
    # Coordinate conversions
    R_CAM_TO_WORLD = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64)
    R_SMPL_TO_BLENDER = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float64)
    
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
    
    # Apply frame 0 with conversions
    Mr_camera = R_root[0]
    Mr_world = R_CAM_TO_WORLD @ Mr_camera @ R_CAM_TO_WORLD.T
    Mr_blender = R_SMPL_TO_BLENDER @ Mr_world @ R_SMPL_TO_BLENDER.T
    
    m = Matrix(((float(Mr_blender[0,0]), float(Mr_blender[0,1]), float(Mr_blender[0,2])),
                (float(Mr_blender[1,0]), float(Mr_blender[1,1]), float(Mr_blender[1,2])),
                (float(Mr_blender[2,0]), float(Mr_blender[2,1]), float(Mr_blender[2,2]))))
    q = m.to_quaternion()
    
    bpy.context.scene.frame_set(1)
    pb = arm.pose.bones['pelvis']
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = q
    bpy.context.view_layer.update()
    
    print(f"\n✓ Applied converted rotation to frame 1")
    print(f"  Open {args.out} in Blender GUI to visually check orientation")
    
    # Save
    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    print(f"✓ Saved: {args.out}\n")


if __name__ == '__main__':
    main()

