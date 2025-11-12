#!/usr/bin/env python3
"""
Debug script to check SMPL-X armature orientation in Blender before FBX export.
This helps identify if the issue is in Blender or in FBX export.

Run:
  blender -b -P tools/blender/debug_smplx_orientation.py -- \
    --npz tmp/test_smoothed.npz
"""

from __future__ import annotations
import argparse
import sys
import os
import numpy as np

def parse_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    return ap.parse_args(argv)


def ensure_blender():
    try:
        import bpy
    except Exception as exc:
        raise SystemExit("Run inside Blender") from exc


def load_npz(npz_path: str):
    data = np.load(npz_path)
    return {k: data[k] for k in data.files}


def main_blender(args):
    ensure_blender()
    import bpy
    from mathutils import Matrix, Vector
    
    data = load_npz(args.npz)
    R_root = data['R_root']
    betas = data.get('betas', None)
    
    print("\n" + "="*60)
    print("DEBUG: SMPL-X Armature Orientation Check")
    print("="*60)
    
    # Clean scene
    for obj in list(bpy.data.objects):
        obj.select_set(True)
    if bpy.data.objects:
        bpy.ops.object.delete()
    
    # Create SMPL-X character
    print("\n1. Creating SMPL-X character...")
    bpy.context.window_manager.smplx_tool.smplx_gender = 'female'
    bpy.ops.scene.smplx_add_gender()
    
    # Find armature
    arm = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm = obj
            break
    
    if arm is None:
        raise RuntimeError("No armature created")
    
    print(f"   ✓ Armature: {arm.name}")
    
    # Check armature world matrix
    print(f"\n2. Armature World Matrix:")
    print(f"   Location: {arm.location}")
    print(f"   Rotation (Euler): {arm.rotation_euler}")
    print(f"   Scale: {arm.scale}")
    print(f"   Matrix World:")
    for row in arm.matrix_world:
        print(f"      {[f'{x:7.4f}' for x in row]}")
    
    # Check pelvis bone orientation in rest pose
    if 'pelvis' in arm.data.bones:
        pelvis_bone = arm.data.bones['pelvis']
        print(f"\n3. Pelvis Bone (Edit/Rest Pose):")
        print(f"   Head: {pelvis_bone.head}")
        print(f"   Tail: {pelvis_bone.tail}")
        print(f"   Vector: {pelvis_bone.vector}")
        print(f"   Length: {pelvis_bone.length:.4f}")
        print(f"   Matrix (local):")
        for row in pelvis_bone.matrix_local:
            print(f"      {[f'{x:7.4f}' for x in row]}")
    
    # Apply first frame rotation to see direction
    print(f"\n4. Applying first frame SMPL rotation...")
    Mr = R_root[0]
    print(f"   SMPL R_root[0]:")
    for row in Mr:
        print(f"      {[f'{x:7.4f}' for x in row]}")
    
    # Convert to quaternion and apply
    m = Matrix(((float(Mr[0,0]), float(Mr[0,1]), float(Mr[0,2])),
                (float(Mr[1,0]), float(Mr[1,1]), float(Mr[1,2])),
                (float(Mr[2,0]), float(Mr[2,1]), float(Mr[2,2]))))
    q = m.to_quaternion()
    
    print(f"   Quaternion: {q}")
    
    # Apply to pose bone
    bpy.context.scene.frame_set(1)
    if 'pelvis' in arm.pose.bones:
        pb = arm.pose.bones['pelvis']
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = q
        bpy.context.view_layer.update()
        
        print(f"\n5. Pelvis Pose Bone (after rotation):")
        print(f"   Rotation (Quat): {pb.rotation_quaternion}")
        print(f"   Matrix (pose space):")
        for row in pb.matrix:
            print(f"      {[f'{x:7.4f}' for x in row]}")
        print(f"   Matrix (world space):")
        for row in pb.matrix @ arm.matrix_world:
            print(f"      {[f'{x:7.4f}' for x in row]}")
    
    # Check head bone to see overall orientation
    if 'head' in arm.data.bones:
        head_bone = arm.data.bones['head']
        print(f"\n6. Head Bone (to check up direction):")
        print(f"   Head: {head_bone.head}")
        print(f"   Tail: {head_bone.tail}")
        print(f"   World Head: {arm.matrix_world @ head_bone.head_local}")
        print(f"   World Tail: {arm.matrix_world @ head_bone.tail_local}")
    
    # Check coordinate system axes
    print(f"\n7. Blender Coordinate System Check:")
    print(f"   X-axis (right): {Vector((1, 0, 0))}")
    print(f"   Y-axis (forward): {Vector((0, 1, 0))}")
    print(f"   Z-axis (up): {Vector((0, 0, 1))}")
    
    # Expected SMPL coordinate system
    print(f"\n8. SMPL Coordinate System (expected):")
    print(f"   X-axis (right): (1, 0, 0)")
    print(f"   Y-axis (up): (0, 1, 0)")
    print(f"   Z-axis (forward): (0, 0, 1)")
    
    print("\n" + "="*60)
    print("ANALYSIS:")
    print("="*60)
    print("If head bone's Y-coordinate is NEGATIVE, the skeleton is upside down.")
    print("If pelvis rotation looks correct but Unity shows upside down,")
    print("the issue is in FBX export axis conversion.")
    print("="*60 + "\n")


if __name__ == '__main__':
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    args = parse_args(argv)
    main_blender(args)

