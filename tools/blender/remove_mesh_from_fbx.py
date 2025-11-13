#!/usr/bin/env python3
"""
Remove mesh from FBX file, keeping only skeleton and animation.

Usage:
    blender -b -P remove_mesh_from_fbx.py -- --input input.fbx --output output.fbx
"""

import bpy
import sys
import argparse
from pathlib import Path


def parse_args():
    """Parse command line arguments."""
    # Find the separator '--' in sys.argv
    if '--' in sys.argv:
        argv = sys.argv[sys.argv.index('--') + 1:]
    else:
        argv = []
    
    parser = argparse.ArgumentParser(description='Remove mesh from FBX, keep skeleton and animation')
    parser.add_argument('--input', required=True, help='Input FBX file path')
    parser.add_argument('--output', required=True, help='Output FBX file path')
    
    return parser.parse_args(argv)


def main():
    args = parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    print("=" * 70)
    print("Remove Mesh from FBX")
    print("=" * 70)
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print()
    
    # Clear scene
    print("[1/4] Clearing scene...")
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # Import FBX
    print(f"[2/4] Importing FBX: {input_path}")
    bpy.ops.import_scene.fbx(filepath=str(input_path))
    
    # Find and list all objects
    print("[3/4] Analyzing scene...")
    mesh_objects = []
    armature_objects = []
    other_objects = []
    
    for obj in bpy.data.objects:
        print(f"  Found: {obj.name} (type: {obj.type})")
        if obj.type == 'MESH':
            mesh_objects.append(obj)
        elif obj.type == 'ARMATURE':
            armature_objects.append(obj)
        else:
            other_objects.append(obj)
    
    print(f"\n  Summary:")
    print(f"    Meshes: {len(mesh_objects)}")
    print(f"    Armatures: {len(armature_objects)}")
    print(f"    Others: {len(other_objects)}")
    
    if not armature_objects:
        raise RuntimeError("No armature found in FBX!")
    
    # Delete mesh objects
    if mesh_objects:
        print(f"\n  Removing {len(mesh_objects)} mesh object(s)...")
        bpy.ops.object.select_all(action='DESELECT')
        for mesh_obj in mesh_objects:
            print(f"    Deleting: {mesh_obj.name}")
            mesh_obj.select_set(True)
        bpy.ops.object.delete()
    else:
        print("\n  No mesh objects to remove")
    
    # Select armature for export
    print("\n[4/4] Exporting FBX (skeleton + animation only)...")
    bpy.ops.object.select_all(action='DESELECT')
    for arm_obj in armature_objects:
        arm_obj.select_set(True)
        print(f"  Selected: {arm_obj.name}")
    
    # Set first armature as active
    bpy.context.view_layer.objects.active = armature_objects[0]
    
    # Export FBX
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(output_path),
        use_selection=True,  # Only export selected objects (armature)
        bake_space_transform=True,  # Apply coordinate system transform
        apply_scale_options='FBX_SCALE_ALL',
        use_custom_props=True,
        add_leaf_bones=False,
        bake_anim=True,  # Bake animation
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_simplify_factor=0  # No simplification
    )
    
    print(f"\n✓ Export complete: {output_path}")
    
    # Show file sizes
    input_size = input_path.stat().st_size / (1024 * 1024)  # MB
    output_size = output_path.stat().st_size / (1024 * 1024)  # MB
    print(f"\nFile size comparison:")
    print(f"  Input:  {input_size:.2f} MB")
    print(f"  Output: {output_size:.2f} MB")
    print(f"  Saved:  {input_size - output_size:.2f} MB ({(1 - output_size/input_size)*100:.1f}%)")
    print("=" * 70)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

