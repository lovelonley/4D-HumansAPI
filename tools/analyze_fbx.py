#!/usr/bin/env python3
"""Analyze FBX file details"""
import bpy
import sys
from pathlib import Path

def analyze_fbx(fbx_path):
    """Analyze FBX file and print details"""
    print(f"\n{'='*70}")
    print(f"FBX: {fbx_path}")
    print('='*70)
    
    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Import FBX
    try:
        bpy.ops.import_scene.fbx(filepath=str(fbx_path))
    except Exception as e:
        print(f"Error importing FBX: {e}")
        return
    
    # Get scene info
    scene = bpy.context.scene
    fps = scene.render.fps
    scene_frame_start = scene.frame_start
    scene_frame_end = scene.frame_end
    
    print(f"\n📊 Scene Info:")
    print(f"  FPS: {fps}")
    print(f"  Scene Frame Range: {scene_frame_start} - {scene_frame_end}")
    print(f"  (Note: Scene frame_end is Blender's default, may not reflect actual animation length)")
    
    # Get objects
    armatures = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
    meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH']
    
    print(f"\n🎭 Objects:")
    print(f"  Armatures: {len(armatures)}")
    print(f"  Meshes: {len(meshes)}")
    
    if armatures:
        arm = armatures[0]
        print(f"\n🦴 Armature: {arm.name}")
        print(f"  Bones: {len(arm.data.bones)}")
        
        # Check animation data
        if arm.animation_data and arm.animation_data.action:
            action = arm.animation_data.action
            print(f"\n🎬 Animation Action: {action.name}")
            print(f"  FCurves: {len(action.fcurves)}")
            
            # Count keyframes
            total_keyframes = sum(len(fc.keyframe_points) for fc in action.fcurves)
            print(f"  Total Keyframes: {total_keyframes}")
            
            # Action frame range (THIS IS THE ACTUAL ANIMATION LENGTH!)
            action_start, action_end = action.frame_range
            action_frame_count = int(action_end - action_start + 1)
            action_duration = action_frame_count / fps
            print(f"\n  ✅ ACTUAL Animation Length:")
            print(f"    Frame Range: {action_start:.0f} - {action_end:.0f}")
            print(f"    Total Frames: {action_frame_count}")
            print(f"    Duration: {action_duration:.2f} seconds ({action_duration/60:.2f} minutes)")
            
            # Keyframe range (for verification)
            if action.fcurves:
                sample_fc = action.fcurves[0]
                if len(sample_fc.keyframe_points) > 0:
                    first_key = sample_fc.keyframe_points[0].co[0]
                    last_key = sample_fc.keyframe_points[-1].co[0]
                    print(f"    Keyframe Range: {first_key:.0f} - {last_key:.0f}")
        else:
            print(f"\n⚠️  No animation data found!")
    
    # File size
    file_size = Path(fbx_path).stat().st_size
    print(f"\n💾 File Size: {file_size / (1024*1024):.2f} MB")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: blender -b -P analyze_fbx.py -- <fbx_file>")
        sys.exit(1)
    
    # Get arguments after '--'
    try:
        separator_index = sys.argv.index("--")
        fbx_path = sys.argv[separator_index + 1]
    except (ValueError, IndexError):
        print("Error: Please provide FBX file path after '--'")
        sys.exit(1)
    
    analyze_fbx(fbx_path)
    
    print(f"\n{'='*70}")
    print("✅ Analysis Complete")
    print('='*70)

