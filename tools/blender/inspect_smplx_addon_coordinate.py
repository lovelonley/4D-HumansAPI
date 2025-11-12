#!/usr/bin/env python3
"""
Inspect the SMPL-X Blender Addon's coordinate system.
Check what coordinate system the addon uses for its bones.
"""

import sys
import numpy as np
import math

def main():
    import bpy
    from mathutils import Matrix, Vector, Euler
    
    print("\n" + "="*70)
    print("INSPECTING SMPL-X ADDON COORDINATE SYSTEM")
    print("="*70)
    
    # Clean scene
    for obj in list(bpy.data.objects):
        obj.select_set(True)
    if bpy.data.objects:
        bpy.ops.object.delete()
    
    # Create SMPL-X character
    print("\n[1] Creating SMPL-X character (rest pose)...")
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
    print(f"  Object rotation: {arm.rotation_euler}")
    print(f"  Object location: {arm.location}")
    
    # Check armature coordinate system
    print(f"\n[2] Armature world matrix:")
    for i, row in enumerate(arm.matrix_world):
        print(f"  Row {i}: [{', '.join(f'{x:7.4f}' for x in row)}]")
    
    # Check bone orientations in rest pose
    print(f"\n[3] Key bone positions in rest pose (world space):")
    bones_to_check = ['pelvis', 'spine', 'head', 'left_shoulder', 'right_shoulder']
    for bone_name in bones_to_check:
        if bone_name in arm.data.bones:
            bone = arm.data.bones[bone_name]
            head_world = arm.matrix_world @ bone.head_local
            tail_world = arm.matrix_world @ bone.tail_local
            direction = tail_world - head_world
            print(f"  {bone_name}:")
            print(f"    Head: {head_world}")
            print(f"    Tail: {tail_world}")
            print(f"    Direction: {direction} (length: {direction.length:.4f})")
    
    # Test: Apply a simple 90° rotation around Y axis (should turn left)
    print(f"\n[4] Test: Apply 90° Y-axis rotation to pelvis")
    print(f"  Expected: Character turns left (head moves in -X direction)")
    
    bpy.context.scene.frame_set(1)
    pb = arm.pose.bones['pelvis']
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (0, math.radians(90), 0)
    bpy.context.view_layer.update()
    
    if 'head' in arm.data.bones:
        head_rest = arm.matrix_world @ arm.data.bones['head'].head_local
        head_pose = arm.matrix_world @ arm.pose.bones['head'].matrix @ Vector((0,0,0))
        print(f"  Head rest: {head_rest}")
        print(f"  Head pose: {head_pose}")
        print(f"  Delta X: {head_pose.x - head_rest.x:.4f}")
        print(f"  Delta Y: {head_pose.y - head_rest.y:.4f}")
        print(f"  Delta Z: {head_pose.z - head_rest.z:.4f}")
    
    # Test: Apply 90° X-axis rotation (should lean backward)
    print(f"\n[5] Test: Apply 90° X-axis rotation to pelvis")
    print(f"  Expected: Character leans backward (head moves in +Y direction in Blender)")
    
    bpy.context.scene.frame_set(2)
    pb.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.view_layer.update()
    
    if 'head' in arm.data.bones:
        head_rest = arm.matrix_world @ arm.data.bones['head'].head_local
        head_pose = arm.matrix_world @ arm.pose.bones['head'].matrix @ Vector((0,0,0))
        print(f"  Head rest: {head_rest}")
        print(f"  Head pose: {head_pose}")
        print(f"  Delta X: {head_pose.x - head_rest.x:.4f}")
        print(f"  Delta Y: {head_pose.y - head_rest.y:.4f}")
        print(f"  Delta Z: {head_pose.z - head_rest.z:.4f}")
    
    # Conclusion
    print(f"\n" + "="*70)
    print("COORDINATE SYSTEM ANALYSIS")
    print("="*70)
    print(f"Blender uses: X-right, Y-forward, Z-up")
    print(f"SMPL standard: X-right, Y-up, Z-forward")
    print(f"Unity: X-right, Y-up, Z-forward")
    print(f"\nSMPL-X addon bones are in: ???")
    print(f"Check the test results above to determine!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()

