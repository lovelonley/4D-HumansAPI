#!/usr/bin/env python3
"""
Directly visualize NPZ rotation data in Blender WITHOUT any conversion.
This shows the EXACT orientation of the data as stored in NPZ.
"""

import sys
import numpy as np
import argparse

def parse_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--frame", type=int, default=0, help="Which frame to visualize")
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
    
    print("\n" + "="*70)
    print("VISUALIZING NPZ DATA DIRECTLY (NO CONVERSION)")
    print("="*70)
    print(f"\nNPZ file: {args.npz}")
    print(f"Frame: {args.frame}")
    print(f"Total frames: {R_root.shape[0]}")
    
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
    mesh = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm = obj
        elif obj.type == 'MESH':
            mesh = obj
    
    if not arm:
        sys.exit("ERROR: No armature")
    
    print(f"  ✓ Created: {arm.name}")
    
    # Check rest pose
    if 'head' in arm.data.bones:
        head = arm.data.bones['head']
        head_rest = arm.matrix_world @ head.head_local
        print(f"\n[2] Rest pose check:")
        print(f"  Head position: {head_rest}")
        print(f"  Z coordinate: {head_rest.z:.4f}")
        if head_rest.z > 0:
            print(f"  ✓ Rest pose is CORRECT (head above origin)")
    
    # Apply NPZ data DIRECTLY - NO CONVERSION AT ALL
    print(f"\n[3] Applying NPZ R_root[{args.frame}] DIRECTLY (zero conversion):")
    Mr = R_root[args.frame]
    print(f"  R_root[{args.frame}]:")
    for row in Mr:
        print(f"    [{', '.join(f'{x:7.4f}' for x in row)}]")
    
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
        
        print(f"\n[4] After applying NPZ rotation:")
        print(f"  Pelvis rotation (quat): {pb.rotation_quaternion}")
    
    # Check head position after rotation
    if 'head' in arm.data.bones:
        head_pose_world = arm.matrix_world @ arm.pose.bones['head'].matrix @ Vector((0,0,0))
        print(f"\n[5] Head position after NPZ rotation:")
        print(f"  World position: {head_pose_world}")
        print(f"  Z coordinate: {head_pose_world.z:.4f}")
        
        if head_pose_world.z > 0:
            print(f"\n✓✓✓ NPZ DATA IS CORRECT - head is above origin")
            print(f"    The character is standing upright!")
        else:
            print(f"\n✗✗✗ NPZ DATA IS INVERTED - head is below origin")
            print(f"    The character is upside down!")
    
    # Save a screenshot if possible
    print(f"\n[6] Scene ready for inspection")
    print(f"  - Open this .blend file to see the pose")
    print(f"  - Or take a screenshot in Blender GUI")
    
    # Save blend file
    blend_path = args.npz.replace('.npz', '_visualization.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"\n✓ Saved: {blend_path}")
    
    print("\n" + "="*70)
    print("VISUALIZATION COMPLETE")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()

