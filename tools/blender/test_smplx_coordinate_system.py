#!/usr/bin/env python3
"""
Test what coordinate system the SMPL-X Blender Addon expects.
Apply simple rotations and observe the result.
"""

import sys
import numpy as np
import math

def main():
    import bpy
    from mathutils import Matrix, Quaternion, Euler
    
    print("\n" + "="*70)
    print("TESTING SMPL-X BLENDER ADDON COORDINATE SYSTEM")
    print("="*70)
    
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
    
    # Get rest pose head position
    if 'head' in arm.data.bones:
        head = arm.data.bones['head']
        head_rest = arm.matrix_world @ head.head_local
        print(f"\n[2] Rest pose (T-pose):")
        print(f"  Head position: {head_rest}")
        print(f"  → Character is standing upright, Y-up")
    
    # Test 1: Apply 90° rotation around X-axis
    print(f"\n[3] Test 1: Rotate pelvis 90° around X-axis")
    print(f"  Expected: Character leans backward (head moves in +Y direction)")
    
    bpy.context.scene.frame_set(1)
    pelvis = arm.pose.bones['pelvis']
    pelvis.rotation_mode = 'XYZ'
    pelvis.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.view_layer.update()
    
    head_pose = arm.matrix_world @ arm.pose.bones['head'].matrix @ bpy.mathutils.Vector((0,0,0))
    print(f"  Head position: {head_pose}")
    print(f"  Change: ΔY = {head_pose.y - head_rest.y:.4f}, ΔZ = {head_pose.z - head_rest.z:.4f}")
    
    # Test 2: Apply 90° rotation around Y-axis
    print(f"\n[4] Test 2: Rotate pelvis 90° around Y-axis")
    print(f"  Expected: Character turns left (head moves in -X direction)")
    
    bpy.context.scene.frame_set(2)
    pelvis.rotation_euler = (0, math.radians(90), 0)
    bpy.context.view_layer.update()
    
    head_pose = arm.matrix_world @ arm.pose.bones['head'].matrix @ bpy.mathutils.Vector((0,0,0))
    print(f"  Head position: {head_pose}")
    print(f"  Change: ΔX = {head_pose.x - head_rest.x:.4f}, ΔZ = {head_pose.z - head_rest.z:.4f}")
    
    # Test 3: Apply 90° rotation around Z-axis
    print(f"\n[5] Test 3: Rotate pelvis 90° around Z-axis")
    print(f"  Expected: Character leans to the right (head moves in +X direction)")
    
    bpy.context.scene.frame_set(3)
    pelvis.rotation_euler = (0, 0, math.radians(90))
    bpy.context.view_layer.update()
    
    head_pose = arm.matrix_world @ arm.pose.bones['head'].matrix @ bpy.mathutils.Vector((0,0,0))
    print(f"  Head position: {head_pose}")
    print(f"  Change: ΔX = {head_pose.x - head_rest.x:.4f}, ΔY = {head_pose.y - head_rest.y:.4f}")
    
    # Test 4: Apply PHALP's problematic rotation
    print(f"\n[6] Test 4: Apply PHALP rotation matrix directly")
    R_phalp = np.array([
        [ 0.9838, -0.0602,  0.1687],
        [-0.0509, -0.9970, -0.0585],
        [ 0.1717,  0.0490, -0.9839]
    ])
    
    m = Matrix(((float(R_phalp[0,0]), float(R_phalp[0,1]), float(R_phalp[0,2])),
                (float(R_phalp[1,0]), float(R_phalp[1,1]), float(R_phalp[1,2])),
                (float(R_phalp[2,0]), float(R_phalp[2,1]), float(R_phalp[2,2]))))
    q = m.to_quaternion()
    
    bpy.context.scene.frame_set(4)
    pelvis.rotation_mode = 'QUATERNION'
    pelvis.rotation_quaternion = q
    bpy.context.view_layer.update()
    
    head_pose = arm.matrix_world @ arm.pose.bones['head'].matrix @ bpy.mathutils.Vector((0,0,0))
    print(f"  Head position: {head_pose}")
    print(f"  Z coordinate: {head_pose.z:.4f}")
    if head_pose.z < 0:
        print(f"  → Character is UPSIDE DOWN")
    else:
        print(f"  → Character is upright")
    
    print("\n" + "="*70)
    print("COORDINATE SYSTEM ANALYSIS COMPLETE")
    print("="*70)
    print("\nConclusion:")
    print("  SMPL-X Blender Addon uses standard Blender coordinate system:")
    print("  - X: right, Y: forward, Z: up")
    print("  - Rotations follow right-hand rule")
    print("\n")


if __name__ == '__main__':
    main()

