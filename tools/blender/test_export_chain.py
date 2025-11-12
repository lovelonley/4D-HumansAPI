#!/usr/bin/env python3
"""
Complete diagnostic test: Create SMPL-X character, check orientation at each step.

Run:
  blender -b -P tools/blender/test_export_chain.py
"""

import bpy
import sys
from mathutils import Matrix, Euler
import math

print("\n" + "="*70)
print("COMPLETE EXPORT CHAIN DIAGNOSTIC")
print("="*70)

# Clean scene
for obj in list(bpy.data.objects):
    obj.select_set(True)
if bpy.data.objects:
    bpy.ops.object.delete()

# Step 1: Create SMPL-X character
print("\n[Step 1] Creating SMPL-X character...")
bpy.context.window_manager.smplx_tool.smplx_gender = 'female'
bpy.ops.scene.smplx_add_gender()

arm = None
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        arm = obj
        break

if not arm:
    sys.exit("ERROR: No armature created")

print(f"  ✓ Created: {arm.name}")
print(f"  World Matrix:")
for i, row in enumerate(arm.matrix_world):
    print(f"    [{', '.join(f'{x:7.4f}' for x in row)}]")

# Step 2: Check rest pose orientation
print("\n[Step 2] Checking rest pose bone orientations...")
if 'pelvis' in arm.data.bones:
    pelvis = arm.data.bones['pelvis']
    print(f"  Pelvis:")
    print(f"    Head: {pelvis.head}")
    print(f"    Tail: {pelvis.tail}")
    print(f"    Vector: {pelvis.vector}")
    print(f"    Matrix Local:")
    for row in pelvis.matrix_local:
        print(f"      [{', '.join(f'{x:7.4f}' for x in row)}]")

if 'head' in arm.data.bones:
    head = arm.data.bones['head']
    print(f"  Head bone:")
    print(f"    World Head: {arm.matrix_world @ head.head_local}")
    print(f"    World Tail: {arm.matrix_world @ head.tail_local}")
    head_world = arm.matrix_world @ head.head_local
    if head_world.z > 0:
        print(f"    ✓ Head is above origin (Z={head_world.z:.4f})")
    else:
        print(f"    ✗ Head is below origin (Z={head_world.z:.4f}) - INVERTED!")

# Step 3: Test different FBX export settings
print("\n[Step 3] Testing FBX export with different settings...")

test_configs = [
    {
        "name": "Config A: Native Blender axes, no bake",
        "settings": {
            "bake_space_transform": False,
            "axis_forward": 'Y',
            "axis_up": 'Z'
        }
    },
    {
        "name": "Config B: Unity axes, with bake",
        "settings": {
            "bake_space_transform": True,
            "axis_forward": '-Z',
            "axis_up": 'Y'
        }
    },
    {
        "name": "Config C: Unity axes, no bake",
        "settings": {
            "bake_space_transform": False,
            "axis_forward": '-Z',
            "axis_up": 'Y'
        }
    },
]

for i, config in enumerate(test_configs):
    print(f"\n  Testing {config['name']}...")
    fbx_path = f"/tmp/test_export_{i}.fbx"
    
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    
    try:
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            use_selection=True,
            object_types={'ARMATURE'},
            add_leaf_bones=False,
            primary_bone_axis='Y',
            secondary_bone_axis='X',
            **config['settings']
        )
        print(f"    ✓ Exported to {fbx_path}")
        
        # Re-import and check
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        
        bpy.ops.import_scene.fbx(filepath=fbx_path)
        
        reimported_arm = None
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                reimported_arm = obj
                break
        
        if reimported_arm:
            print(f"    Re-imported armature: {reimported_arm.name}")
            print(f"    Location: {reimported_arm.location}")
            print(f"    Rotation (Euler): {reimported_arm.rotation_euler}")
            euler = reimported_arm.rotation_euler
            print(f"      X: {math.degrees(euler.x):.2f}°")
            print(f"      Y: {math.degrees(euler.y):.2f}°")
            print(f"      Z: {math.degrees(euler.z):.2f}°")
            
            if 'head' in reimported_arm.data.bones:
                head = reimported_arm.data.bones['head']
                head_world = reimported_arm.matrix_world @ head.head_local
                print(f"    Head bone world pos: {head_world}")
                if head_world.z > 0:
                    print(f"    ✓ Correct orientation")
                else:
                    print(f"    ✗ INVERTED")
        
        # Restore original for next test
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        bpy.context.window_manager.smplx_tool.smplx_gender = 'female'
        bpy.ops.scene.smplx_add_gender()
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                arm = obj
                break
                
    except Exception as e:
        print(f"    ✗ Export failed: {e}")

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)

