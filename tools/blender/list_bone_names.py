#!/usr/bin/env python3
"""List all bone names in an FBX file"""
import bpy
import sys
from pathlib import Path

def list_bones(fbx_path):
    """List all bones in FBX file"""
    print(f"\n{'='*70}")
    print(f"Listing bones in: {fbx_path}")
    print('='*70)
    
    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Import FBX
    try:
        bpy.ops.import_scene.fbx(filepath=str(fbx_path))
    except Exception as e:
        print(f"Error importing FBX: {e}")
        return
    
    # Get armatures
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    
    if not armatures:
        print("No armature found!")
        return
    
    arm = armatures[0]
    print(f"\nArmature: {arm.name}")
    print(f"Total bones: {len(arm.data.bones)}\n")
    
    print("Bone names:")
    print("-" * 70)
    for i, bone in enumerate(arm.data.bones, 1):
        print(f"{i:3d}. {bone.name}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: blender -b -P list_bone_names.py -- <fbx_file>")
        sys.exit(1)
    
    # Get arguments after '--'
    try:
        separator_index = sys.argv.index("--")
        fbx_path = sys.argv[separator_index + 1]
    except (ValueError, IndexError):
        print("Error: Please provide FBX file path after '--'")
        sys.exit(1)
    
    list_bones(fbx_path)
