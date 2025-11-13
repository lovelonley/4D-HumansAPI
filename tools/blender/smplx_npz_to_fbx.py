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
  - Official SMPL-X Blender Addon (Meshcapade) installed and enabled
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
    ap.add_argument("--gender", default="female", choices=["female", "male", "neutral"], help="Body gender")
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


def rotmat_to_rodrigues(R: np.ndarray) -> np.ndarray:
    """
    Convert 3x3 rotation matrix to Rodrigues vector (axis-angle representation).
    
    Rodrigues vector: rotation_axis * rotation_angle
    - The direction of the vector is the rotation axis
    - The magnitude of the vector is the rotation angle in radians
    
    This is the format expected by the SMPL-X Blender addon.
    
    Implementation based on cv2.Rodrigues formula (no scipy dependency).
    """
    # Ensure it's a proper numpy array
    R = np.array(R, dtype=np.float64)
    
    # Calculate rotation angle from trace
    # trace = 1 + 2*cos(theta)
    trace = R[0,0] + R[1,1] + R[2,2]
    theta = np.arccos(np.clip((trace - 1.0) / 2.0, -1.0, 1.0))
    
    # Small angle approximation
    if theta < 1e-8:
        return np.zeros(3, dtype=np.float64)
    
    # Extract rotation axis from skew-symmetric part
    # For small angles near pi, use different formula
    if np.abs(theta - np.pi) < 1e-3:
        # Near 180 degrees - use diagonal elements
        # Find the largest diagonal element
        diag = np.array([R[0,0], R[1,1], R[2,2]])
        k = np.argmax(diag)
        
        # Compute axis from the column with largest diagonal
        axis = np.zeros(3)
        axis[k] = np.sqrt((R[k, k] + 1.0) / 2.0)
        
        for i in range(3):
            if i != k:
                axis[i] = R[k, i] / (2.0 * axis[k])
        
        axis = axis / np.linalg.norm(axis)
    else:
        # Normal case: extract from skew-symmetric part
        axis = np.array([
            R[2, 1] - R[1, 2],
            R[0, 2] - R[2, 0],
            R[1, 0] - R[0, 1]
        ], dtype=np.float64)
        
        axis = axis / (2.0 * np.sin(theta))
    
    # Rodrigues vector = axis * angle
    rodrigues = axis * theta
    return rodrigues.astype(np.float64)


# COORDINATE SYSTEM FLOW (based on code analysis):
# 1. PHALP outputs SMPL data in Y-down coordinate system (camera/OpenCV convention)
# 2. PHALP renders video with 180° X-axis rotation to flip Y-down → Y-up (see py_renderer.py:136)
# 3. Our NPZ data is extracted directly from PKL without conversion → still Y-down
# 4. We need to apply the same 180° X-axis rotation that PHALP uses for rendering
# 5. Then SMPL-X addon's correct_for_anim_format applies -90° X-axis to go Y-up → Z-up

# 180° X-axis rotation matrix (Y-down → Y-up, same as PHALP renderer)
R_FLIP_Y = np.array([
    [1.0,  0.0,  0.0],
    [0.0, -1.0,  0.0],
    [0.0,  0.0, -1.0]
], dtype=np.float64)

print("[coord] Coordinate system conversion:")
print("[coord]   Input: Y-down (PHALP/OpenCV convention)")
print("[coord]   Step 1: Apply 180° X-axis rotation (Y-down → Y-up)")
print("[coord]   Step 2: Addon applies -90° X-axis (Y-up → Z-up Blender)")
print("[coord]   Step 3: FBX export (Z-up → Y-up Unity)")


def create_smplx_character_with_shape(gender: str = "female", betas: np.ndarray | None = None) -> tuple:
    """
    Create SMPL-X character by directly loading from addon's data folder.
    
    Args:
        gender: Body gender ("female", "male", or "neutral")
        betas: Optional shape parameters (T, 10) or (10,)
    
    Returns:
        (armature_object, mesh_object) tuple
    """
    import bpy
    import os
    import addon_utils
    
    # Clean scene
    bpy.ops.object.select_all(action='SELECT')
    if bpy.context.selected_objects:
        bpy.ops.object.delete()

    # Find addon path
    addon_name = "meshcapade_addon"
    for mod in addon_utils.modules():
        if mod.__name__ == addon_name:
            addon_path = os.path.dirname(mod.__file__)
            break
    else:
        raise RuntimeError(f"Cannot find {addon_name} path")
    
    # Load SMPL-X model from addon's data folder
    blend_file = os.path.join(addon_path, "data", "smplx.blend")
    object_name = f"SMPLX-mesh-{gender}"
    objects_path = os.path.join(blend_file, "Object")
    
    print(f"[smplx] Loading model from: {blend_file}")
    print(f"[smplx] Object: {object_name}")
    
    # Use bpy.data.libraries.load instead of bpy.ops.wm.append for better control
    with bpy.data.libraries.load(blend_file, link=False) as (data_from, data_to):
        if object_name in data_from.objects:
            data_to.objects = [object_name]
        else:
            raise RuntimeError(f"Object {object_name} not found in {blend_file}")
    
    # Link loaded objects to scene
    for obj in data_to.objects:
        if obj is not None:
            bpy.context.collection.objects.link(obj)
    
    # Find armature and mesh
    arm = None
    mesh = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm = obj
        elif obj.type == 'MESH':
            mesh = obj
    
    if arm is None or mesh is None:
        raise RuntimeError("SMPL-X armature or mesh not loaded")
    
    # Set properties on the mesh (same as addon does)
    mesh['gender'] = gender
    mesh['SMPL_version'] = "SMPLX"
    bpy.context.view_layer.objects.active = mesh
    
    print(f"[smplx] Loaded armature: {arm.name}, mesh: {mesh.name}")
    
    # Apply body shape (betas) if provided
    if betas is not None and mesh is not None:
        # Use the first frame's betas (assuming consistent shape across frames)
        betas_vec = betas[0] if betas.ndim > 1 else betas
        
        # The SMPL-X addon stores shape keys in the mesh
        # Shape keys are named: Shape000, Shape001, ..., Shape299 for SMPL-X
        if mesh.data.shape_keys and mesh.data.shape_keys.key_blocks:
            num_betas = min(len(betas_vec), 10)  # Use first 10 betas (body shape)
            print(f"[smplx] Applying {num_betas} shape parameters")
            
            for i in range(num_betas):
                shape_key_name = f"Shape{i:03d}"
                if shape_key_name in mesh.data.shape_keys.key_blocks:
                    value = float(betas_vec[i])
                    mesh.data.shape_keys.key_blocks[shape_key_name].value = value
                    print(f"[smplx]   {shape_key_name} = {value:.4f}")
            
            # Update joint locations based on shape (same as addon's OP_LoadAvatar:194)
            # Active object must be the mesh for this operator to work
            bpy.context.view_layer.objects.active = mesh
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.update_joint_locations('EXEC_DEFAULT')
            print(f"[smplx] Body shape applied and joint locations updated")
    
    return arm, mesh


def set_pose_from_rodrigues_inline(armature, bone_name, rodrigues, frame=1):
    """
    Inline implementation of addon's set_pose_from_rodrigues function.
    Converts Rodrigues vector to quaternion and sets bone rotation.
    """
    from mathutils import Vector, Quaternion
    
    rod = Vector((float(rodrigues[0]), float(rodrigues[1]), float(rodrigues[2])))
    angle_rad = rod.length
    if angle_rad > 1e-8:
        axis = rod.normalized()
    else:
        axis = Vector((0, 0, 1))  # Default axis if angle is zero
    
    pbone = armature.pose.bones[bone_name]
    pbone.rotation_mode = 'QUATERNION'
    quat = Quaternion(axis, angle_rad)
    pbone.rotation_quaternion = quat
    pbone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    
    if bone_name == 'pelvis':
        pbone.keyframe_insert('location', frame=frame)


def correct_for_anim_format_inline(armature):
    """
    Inline implementation of addon's correct_for_anim_format for AMASS.
    Applies -90° X-axis rotation to root bone to convert Y-up to Z-up.
    """
    from mathutils import Quaternion
    import math
    
    # Find root bone (it's usually called 'root' in SMPL-X addon armatures)
    if 'root' in armature.pose.bones:
        bone_name = "root"
        armature.pose.bones[bone_name].rotation_mode = 'QUATERNION'
        armature.pose.bones[bone_name].rotation_quaternion = Quaternion((1.0, 0.0, 0.0), math.radians(-90))
        import bpy
        armature.pose.bones[bone_name].keyframe_insert('rotation_quaternion', frame=bpy.data.scenes[0].frame_current)
        armature.pose.bones[bone_name].keyframe_insert(data_path="location", frame=bpy.data.scenes[0].frame_current)


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
    Bake SMPL rotations into SMPL-X armature animation using Rodrigues vectors.
    
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
    
    print(f"[bake] Applying coordinate system conversion (Y-down → Y-up)")
    print(f"[bake] This matches PHALP's rendering transformation")
    
    # Apply 180° X-axis rotation to flip Y-down → Y-up (same as PHALP renderer)
    # For rotation matrices: R_new = R_FLIP_Y @ R_old @ R_FLIP_Y.T
    R_root_flipped = np.array([R_FLIP_Y @ R @ R_FLIP_Y.T for R in R_root])
    R_body_flipped = np.array([[R_FLIP_Y @ R @ R_FLIP_Y.T for R in frame] for frame in R_body])
    
    print(f"[bake] Converting rotation matrices to Rodrigues vectors")

    pbones = arm_obj.pose.bones
    
    # Bake each frame
    for f in range(frame_idx.shape[0]):
        frame = int(frame_idx[f])
        bpy.context.scene.frame_set(frame)

        # Root bone (pelvis) - global orientation
        if 'pelvis' in pbones:
            # Convert rotation matrix to Rodrigues vector (use flipped data)
            rodrigues_root = rotmat_to_rodrigues(R_root_flipped[f])
            
            # Set pose using inline function (same as addon)
            set_pose_from_rodrigues_inline(arm_obj, 'pelvis', rodrigues_root, frame=frame)
            
            # Root motion (translation)
            if with_root_motion and camera is not None:
                cam = camera[f]
                # AMASS uses Y-up, correct_for_anim_format_inline will handle conversion
                # Scale factor: 100 (addon expects cm, we have meters)
                tx, ty, tz = float(cam[0]) * 100, float(cam[1]) * 100, float(cam[2]) * 100
                
                pb = pbones['pelvis']
                pb.location = (tx, ty, tz)
                pb.keyframe_insert(data_path='location', frame=frame)

        # Body joints (23 joints in SMPL body_pose)
        for idx, joint_name in enumerate(SMPL_BODY_NAMES):
            if joint_name == 'pelvis':
                continue  # Already handled as root
            
            if joint_name not in pbones:
                print(f"[warn] Joint not found in armature: {joint_name}")
                continue
            
            # Convert rotation matrix to Rodrigues vector (use flipped data)
            rodrigues = rotmat_to_rodrigues(R_body_flipped[f, idx])
            
            # Set pose using inline function
            set_pose_from_rodrigues_inline(arm_obj, joint_name, rodrigues, frame=frame)
    
    # Set animation range
    bpy.context.scene.frame_start = int(frame_idx.min())
    bpy.context.scene.frame_end = int(frame_idx.max())

    # Apply coordinate system correction for AMASS format (Y-up -> Z-up Blender)
    correct_for_anim_format_inline(arm_obj)
    print(f"[bake] Applied AMASS coordinate system correction (Y-up -> Z-up)")
    
    # Ensure animation data exists
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    if arm_obj.animation_data.action is None:
        arm_obj.animation_data.action = bpy.data.actions.new(name='Take 001')

    print(f"[bake] Baked {frame_idx.shape[0]} frames (range: {frame_idx.min()}-{frame_idx.max()})")


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
    
    # Ensure SMPL-X addon is enabled
    import bpy
    import addon_utils
    addon_name = "meshcapade_addon"
    loaded_default, loaded_state = addon_utils.check(addon_name)
    if not loaded_state:
        addon_utils.enable(addon_name, default_set=True)
        print(f"[addon] Enabled {addon_name}")
    else:
        print(f"[addon] {addon_name} already enabled")
    
    # Verify the operator is available
    if not hasattr(bpy.ops.object, 'update_joint_locations'):
        raise RuntimeError("SMPL-X addon not properly loaded: update_joint_locations operator not found")
    
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
    print(f"[load] Gender: {args.gender}")
    if betas is not None:
        print(f"[load] Betas shape: {betas.shape}")
    else:
        print("[load] No betas found, using default body shape")
    
    # Create SMPL-X character with body shape using official addon
    arm_obj, mesh_obj = create_smplx_character_with_shape(args.gender, betas)
    
    # Bake animation using addon's functions
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
    
    # Export FBX (keep mesh for proper export)
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
