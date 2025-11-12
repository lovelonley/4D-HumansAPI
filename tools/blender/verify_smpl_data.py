#!/usr/bin/env python3
"""
Verify if 4D-Humans SMPL output data is correct by visualizing it directly.
This uses the official SMPL-X model to render the pose without any conversion.

Run:
  blender -b -P tools/blender/verify_smpl_data.py -- --npz tmp/test.npz
"""

import argparse
import sys
import numpy as np

def parse_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    return ap.parse_args(argv)


def main():
    import bpy
    from mathutils import Matrix, Vector
    
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    args = parse_args(argv)
    
    # Load NPZ
    data = np.load(args.npz)
    R_root = data['R_root']
    R_body = data['R_body']
    betas = data.get('betas', None)
    
    print("\n" + "="*70)
    print("VERIFYING SMPL DATA FROM NPZ")
    print("="*70)
    print(f"\nNPZ file: {args.npz}")
    print(f"Note: This NPZ should contain world-space rotations (Y-up)")
    print(f"      after coordinate system conversion from PHALP camera space.")
    
    # Clean scene
    for obj in list(bpy.data.objects):
        obj.select_set(True)
    if bpy.data.objects:
        bpy.ops.object.delete()
    
    # Create SMPL-X character
    print("\n[1] Creating SMPL-X character...")
    bpy.context.window_manager.smplx_tool.smplx_gender = 'female'
    bpy.ops.scene.smplx_add_gender()
    
    arm = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm = obj
            break
    
    if not arm:
        sys.exit("ERROR: No armature")
    
    print(f"  ✓ Created: {arm.name}")
    
    # Check initial orientation (rest pose)
    if 'head' in arm.data.bones:
        head = arm.data.bones['head']
        head_world = arm.matrix_world @ head.head_local
        print(f"\n[2] Rest pose check:")
        print(f"  Head bone world position: {head_world}")
        print(f"  Z coordinate: {head_world.z:.4f}")
        if head_world.z > 0:
            print(f"  ✓ Rest pose is CORRECT (head above origin)")
        else:
            print(f"  ✗ Rest pose is WRONG (head below origin)")
    
    # Apply FIRST FRAME of SMPL data directly (should already be in world space)
    print(f"\n[3] Applying SMPL data (frame 0) directly:")
    Mr = R_root[0]
    print(f"  R_root[0]:")
    for row in Mr:
        print(f"    [{', '.join(f'{x:7.4f}' for x in row)}]")
    print(f"  (This should be in world space Y-up if conversion was applied)")
    
    # Convert to quaternion
    m = Matrix(((float(Mr[0,0]), float(Mr[0,1]), float(Mr[0,2])),
                (float(Mr[1,0]), float(Mr[1,1]), float(Mr[1,2])),
                (float(Mr[2,0]), float(Mr[2,1]), float(Mr[2,2]))))
    q = m.to_quaternion()
    
    bpy.context.scene.frame_set(1)
    if 'pelvis' in arm.pose.bones:
        pb = arm.pose.bones['pelvis']
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = q
        bpy.context.view_layer.update()
        
        print(f"\n[4] After applying SMPL rotation:")
        print(f"  Pelvis rotation (quat): {pb.rotation_quaternion}")
    
    # Check head position after rotation
    if 'head' in arm.data.bones:
        head = arm.data.bones['head']
        # Get world position considering pose
        head_pose_world = arm.matrix_world @ arm.pose.bones['head'].matrix @ Vector((0,0,0))
        print(f"\n[5] Head position after SMPL rotation:")
        print(f"  World position: {head_pose_world}")
        print(f"  Z coordinate: {head_pose_world.z:.4f}")
        
        if head_pose_world.z > 0:
            print(f"\n✓✓✓ DATA IS CORRECT - head is above origin")
            print(f"    Coordinate system conversion was successful!")
        else:
            print(f"\n✗✗✗ DATA IS STILL WRONG - head is below origin")
            print(f"    Coordinate system conversion failed or not applied!")
    
    print("\n" + "="*70)
    print("VERIFICATION COMPLETE")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()

