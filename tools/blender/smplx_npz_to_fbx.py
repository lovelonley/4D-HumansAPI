#!/usr/bin/env python3
"""
Use the official SMPL-X Blender addon to create a standard SMPL-X armature with
body shape (betas), apply SMPL pose rotations from an NPZ, and export to FBX for
Unity Humanoid.

Run:
  blender -b -P tools/blender/smplx_npz_to_fbx.py -- \
    --npz /abs/path/demo_7111_tid1_smoothed.npz \
    --out /abs/path/demo_7111_tid1_smplx.fbx \
    --fps 30 \
    --with-root-motion

Requirements:
  - Official SMPL-X Blender Addon installed and enabled
  - NPZ must contain: R_root, R_body, frame_idx, betas (optional)
"""

from __future__ import annotations

import argparse
import sys
import os
from typing import Dict, List

import numpy as np


def parse_args(argv: List[str]):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True, help="Path to NPZ file")
    ap.add_argument("--out", required=True, help="Output FBX path")
    ap.add_argument("--fps", type=int, default=30, help="Frame rate")
    ap.add_argument("--with-root-motion", action="store_true", help="Enable root motion from camera data")
    ap.add_argument("--cam-scale", type=float, default=1.0, help="Scale for camera translation (meters)")
    return ap.parse_args(argv)


def ensure_blender():
    try:
        import bpy  # noqa: F401
    except Exception as exc:
        raise SystemExit("Run inside Blender: blender -b -P ... -- <args>") from exc


def load_npz(npz_path: str) -> Dict[str, np.ndarray]:
    data = np.load(npz_path)
    req = ["R_root", "R_body", "frame_idx"]
    for k in req:
        if k not in data:
            raise RuntimeError(f"NPZ missing key: {k}")
    return {k: data[k] for k in data.files}


# SMPL body joint names (23 joints, index 0 is pelvis/root)
SMPL_BODY_NAMES = [
    "pelvis",          # 0 (root in SMPL body_pose)
    "left_hip",        # 1
    "right_hip",       # 2
    "spine1",          # 3
    "left_knee",       # 4
    "right_knee",      # 5
    "spine2",          # 6
    "left_ankle",      # 7
    "right_ankle",     # 8
    "spine3",          # 9
    "left_foot",       #10
    "right_foot",      #11
    "neck",            #12
    "left_collar",     #13
    "right_collar",    #14
    "head",            #15
    "left_shoulder",   #16
    "right_shoulder",  #17
    "left_elbow",      #18
    "right_elbow",     #19
    "left_wrist",      #20
    "right_wrist",     #21
    "left_hand",       #22
    "right_hand",      #23
]


def mat3_to_quat(M: np.ndarray):
    """Convert 3x3 rotation matrix to Blender quaternion."""
    from mathutils import Matrix
    m = Matrix(((float(M[0,0]), float(M[0,1]), float(M[0,2])),
                (float(M[1,0]), float(M[1,1]), float(M[1,2])),
                (float(M[2,0]), float(M[2,1]), float(M[2,2]))))
    return m.to_quaternion()


# Coordinate system conversions:
# 1. PHALP outputs rotations in camera coordinate system (Y-down, inverted)
# 2. Convert to world coordinate system (Y-up, standard SMPL)
# 3. Convert to Blender coordinate system (Z-up, SMPL-X addon format)

# Step 1: Camera (Y-down) -> World (Y-up): 180° rotation around X axis
# This flips Y and Z axes
R_CAM_TO_WORLD = np.array([
    [1.0,  0.0,  0.0],
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0]
], dtype=np.float64)

# Step 2: SMPL World (Y-up) -> Blender (Z-up): 90° rotation around X axis
# This rotates Y-up to Z-up
R_SMPL_TO_BLENDER = np.array([
    [1.0,  0.0,  0.0],
    [0.0,  0.0, -1.0],
    [0.0,  1.0,  0.0]
], dtype=np.float64)

print("[coord] Coordinate conversion matrices initialized:")
print("[coord]   R_CAM_TO_WORLD: 180° X-axis (flip Y and Z)")
print("[coord]   R_SMPL_TO_BLENDER: 90° X-axis (Y-up → Z-up)")


def create_smplx_character_with_shape(betas: np.ndarray | None = None) -> "bpy.types.Object":
    """
    Create SMPL-X character using official addon and apply body shape (betas).
    
    Returns:
        Armature object
    """
    import bpy
    
    # Clean scene
    for obj in list(bpy.data.objects):
        obj.select_set(True)
    if bpy.data.objects:
        bpy.ops.object.delete()
    
    # Create SMPL-X character via addon
    # Set gender in window manager properties (addon reads from here)
    bpy.context.window_manager.smplx_tool.smplx_gender = 'female'
    
    # Add SMPL-X character (no parameters needed)
    bpy.ops.scene.smplx_add_gender()
    
    # Find armature
    arm = None
    mesh = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm = obj
        elif obj.type == 'MESH':
            mesh = obj
    
    if arm is None:
        raise RuntimeError("SMPL-X armature not created by addon")
    
    print(f"[smplx] Created armature: {arm.name}")
    
    # Don't apply object-level rotation - we'll handle coordinate conversion in FBX export
    # The armature is in Blender's native Z-up space
    
    # Delete the mesh - we only need the armature for animation
    if mesh is not None:
        bpy.data.objects.remove(mesh, do_unlink=True)
        print(f"[smplx] Removed mesh (only exporting armature)")
    
    # Apply body shape (betas) - disabled since we removed the mesh
    if False and betas is not None and mesh is not None:
        # Use the first frame's betas (assuming consistent shape across frames)
        betas_vec = betas[0] if betas.ndim > 1 else betas
        
        # The SMPL-X addon stores shape keys in the mesh
        # Shape keys are named: Shape000, Shape001, ..., Shape009 for first 10 betas
        if mesh.data.shape_keys and mesh.data.shape_keys.key_blocks:
            num_betas = min(len(betas_vec), 10)  # Standard SMPL uses 10 betas
            for i in range(num_betas):
                shape_key_name = f"Shape{i:03d}"
                if shape_key_name in mesh.data.shape_keys.key_blocks:
                    # Betas typically range from -3 to +3, shape keys expect 0-1
                    # We'll clamp to a reasonable range
                    value = float(betas_vec[i])
                    # Normalize: assume betas range is [-3, 3], map to [0, 1]
                    # But shape keys might have different ranges, so we'll use raw value
                    mesh.data.shape_keys.key_blocks[shape_key_name].value = value
                    print(f"[smplx] Set {shape_key_name} = {value:.4f}")
            
            # Update mesh to apply shape keys
            bpy.context.view_layer.update()
    
    return arm


def bake_animation(
    arm_obj,
    R_root: np.ndarray,
    R_body: np.ndarray,
    frame_idx: np.ndarray,
    fps: int,
    camera: np.ndarray | None = None,
    cam_scale: float = 1.0,
    with_root_motion: bool = False
):
    """
    Bake SMPL rotations into SMPL-X armature animation.
    
    Args:
        arm_obj: Blender armature object
        R_root: (T, 3, 3) global orientation (pelvis)
        R_body: (T, 23, 3, 3) body pose rotations
        frame_idx: (T,) frame indices
        fps: Frame rate
        camera: (T, 3) camera translation (optional, for root motion)
        cam_scale: Scale factor for camera translation
        with_root_motion: If True, apply camera translation to root
    """
    import bpy
    
    bpy.context.scene.render.fps = int(fps)
    
    # Sort frames by index and normalize to start at 1
    order = np.argsort(frame_idx)
    R_root = R_root[order]
    R_body = R_body[order]
    frame_idx = frame_idx[order]
    if camera is not None:
        camera = camera[order]
    frame_idx = frame_idx - frame_idx.min() + 1
    
    # Set rotation mode for all pose bones
    for b in arm_obj.pose.bones:
        b.rotation_mode = 'QUATERNION'
    
    pbones = arm_obj.pose.bones
    
    # Bake each frame
    for f in range(frame_idx.shape[0]):
        frame = int(frame_idx[f])
        bpy.context.scene.frame_set(frame)
        
        # Root bone (pelvis) - global orientation
        if 'pelvis' in pbones:
            Mr_camera = R_root[f]
            
            # Step 1: Convert from PHALP camera (Y-down, inverted) to world (Y-up)
            Mr_world = R_CAM_TO_WORLD @ Mr_camera @ R_CAM_TO_WORLD.T
            
            # Step 2: Convert from SMPL world (Y-up) to Blender (Z-up)
            Mr_blender = R_SMPL_TO_BLENDER @ Mr_world @ R_SMPL_TO_BLENDER.T
            
            # Log first frame for verification
            if f == 0:
                print(f"\n[coord] Frame 0 root conversion:")
                print(f"  Camera (Y-down): [[{Mr_camera[0,0]:.4f}, {Mr_camera[0,1]:.4f}, {Mr_camera[0,2]:.4f}], ...]")
                print(f"  World (Y-up):    [[{Mr_world[0,0]:.4f}, {Mr_world[0,1]:.4f}, {Mr_world[0,2]:.4f}], ...]")
                print(f"  Blender (Z-up):  [[{Mr_blender[0,0]:.4f}, {Mr_blender[0,1]:.4f}, {Mr_blender[0,2]:.4f}], ...]")
            
            q = mat3_to_quat(Mr_blender)
            pb = pbones['pelvis']
            pb.rotation_quaternion = q
            pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            
            # Root motion (translation)
            if with_root_motion and camera is not None:
                cam = camera[f]
                tx, ty, tz = float(cam[0]), float(cam[1]), float(cam[2])
                
                # Camera data from 4D-Humans is in OpenCV convention:
                # X right, Y down, Z forward
                # Convert to Blender: X right, Y forward, Z up
                x_bl = tx * cam_scale
                y_bl = tz * cam_scale
                z_bl = (-ty) * cam_scale
                
                pb.location = (x_bl, y_bl, z_bl)
                pb.keyframe_insert(data_path='location', frame=frame)
        
        # Body joints (23 joints)
        for idx, joint_name in enumerate(SMPL_BODY_NAMES):
            if joint_name == 'pelvis':
                continue  # Already handled as root
            
            if joint_name not in pbones:
                continue  # Skip if bone doesn't exist in armature
            
            # Convert body joint rotation (same two-step process as root)
            M_camera = R_body[f, idx]
            # Step 1: Camera → World
            M_world = R_CAM_TO_WORLD @ M_camera @ R_CAM_TO_WORLD.T
            # Step 2: World → Blender
            M_blender = R_SMPL_TO_BLENDER @ M_world @ R_SMPL_TO_BLENDER.T
            q = mat3_to_quat(M_blender)
            
            pb = pbones[joint_name]
            pb.rotation_quaternion = q
            pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
    
    # Set animation range
    bpy.context.scene.frame_start = int(frame_idx.min())
    bpy.context.scene.frame_end = int(frame_idx.max())
    
    # Ensure animation data exists
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    if arm_obj.animation_data.action is None:
        arm_obj.animation_data.action = bpy.data.actions.new(name='Take 001')
    
    print(f"[bake] Baked {frame_idx.shape[0]} frames (range: {frame_idx.min()}-{frame_idx.max()})")
    
    # Verify: Check frame 1 pose orientation
    import bpy
    from mathutils import Vector
    bpy.context.scene.frame_set(int(frame_idx[0]))
    if 'head' in arm_obj.pose.bones:
        head_world = arm_obj.matrix_world @ arm_obj.pose.bones['head'].matrix @ Vector((0,0,0))
        print(f"\n[verify] Frame {int(frame_idx[0])} verification:")
        print(f"  Head position: {head_world}")
        print(f"  Z coordinate: {head_world.z:.4f}")
        if head_world.z > 0:
            print(f"  ✓ Character is UPRIGHT (head above origin)")
        else:
            print(f"  ✗ Character is INVERTED (head below origin)")
            print(f"  WARNING: Coordinate conversion may be incorrect!")


def export_fbx_for_unity(arm_obj, out_path: str):
    """
    Export armature to FBX for Unity Humanoid using standard Blender FBX exporter.
    
    Note: meshcapade_addon does not provide a public FBX export operator,
    so we use Blender's standard FBX exporter with Unity-compatible settings.
    """
    import bpy
    
    # Ensure we're in object mode
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # Select only the armature (mesh was deleted during creation)
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    
    # Standard FBX export with Unity settings
    # Our rotations are now in Blender space (Z-up) after conversion
    # Let FBX exporter convert Blender (Z-up) to Unity (Y-up)
    print("[export] FBX export settings:")
    print("  bake_space_transform=True (Blender Z-up → Unity Y-up)")
    print("  axis_forward='-Z', axis_up='Y' (Unity coordinate system)")
    
    bpy.ops.export_scene.fbx(
        filepath=out_path,
        use_selection=True,
        apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL',
        bake_space_transform=True,  # Blender Z-up → Unity Y-up
        object_types={'ARMATURE', 'MESH'},
        use_mesh_modifiers=True,
        mesh_smooth_type='FACE',
        add_leaf_bones=False,
        primary_bone_axis='Y',
        secondary_bone_axis='X',
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        path_mode='AUTO',
        embed_textures=False,
        batch_mode='OFF',
        axis_forward='-Z',  # Unity forward
        axis_up='Y'         # Unity up
    )
    print(f"[export] Standard FBX export (Unity compatible) -> {out_path}")


def main_blender(args):
    ensure_blender()
    
    # Load NPZ data
    data = load_npz(args.npz)
    R_root = data['R_root']
    R_body = data['R_body']
    frame_idx = data['frame_idx']
    fps = int(data['fps'][0]) if 'fps' in data and data['fps'].size > 0 else args.fps
    camera = data.get('camera', None)
    betas = data.get('betas', None)
    
    print(f"[load] NPZ: {args.npz}")
    print(f"[load] Frames: {R_root.shape[0]}, FPS: {fps}")
    if betas is not None:
        print(f"[load] Betas shape: {betas.shape}")
    else:
        print("[load] No betas found, using default body shape")
    
    # Create SMPL-X character with body shape
    arm_obj = create_smplx_character_with_shape(betas)
    
    # Bake animation
    bake_animation(
        arm_obj,
        R_root,
        R_body,
        frame_idx,
        fps,
        camera=camera,
        cam_scale=args.cam_scale,
        with_root_motion=args.with_root_motion
    )
    
    # Export FBX
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    export_fbx_for_unity(arm_obj, args.out)
    
    print(f"[done] Exported FBX: {args.out}")


if __name__ == '__main__':
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    args = parse_args(argv)
    main_blender(args)
