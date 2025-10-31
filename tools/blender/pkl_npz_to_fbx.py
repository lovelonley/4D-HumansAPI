#!/usr/bin/env python3
"""
Blender headless script: load SMPL rotations from NPZ, create a simple SMPL armature,
bake animation (optionally with root motion), and export to FBX for Unity Humanoid.

Run:
  blender -b -P tools/blender/pkl_npz_to_fbx.py -- \
    --npz /abs/path/to/demo_7111_tid1.npz \
    --out /abs/path/to/demo_7111_tid1.fbx \
    --fps 30 \
    --with-root-motion

Notes:
  - This script intentionally creates an Armature only (no mesh) with SMPL-like names.
  - Bone lengths are approximate (T-pose). Unity Humanoid retargeting will map rotations.
  - NPZ is expected to contain: R_root (N,3,3), R_body (N,23,3,3), camera (N,3), frame_idx (N,), fps (scalar)
"""

from __future__ import annotations

import argparse
import sys
import os
from typing import List, Dict

import numpy as np


def parse_args(argv: List[str]):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--with-root-motion", action="store_true")
    return ap.parse_args(argv)


def load_npz(npz_path: str) -> Dict[str, np.ndarray]:
    data = np.load(npz_path)
    required = ["R_root", "R_body", "camera", "frame_idx"]
    for k in required:
        if k not in data:
            raise RuntimeError(f"NPZ missing key: {k}")
    return {k: data[k] for k in data.files}


"""Unity Humanoid rig bone names and parents (subset that maps well from SMPL)."""
UNITY_BONE_NAMES: List[str] = [
    # Torso
    "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head",
    # Left leg
    "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes",
    # Right leg
    "RightUpperLeg", "RightLowerLeg", "RightFoot", "RightToes",
    # Left arm
    "LeftShoulder", "LeftUpperArm", "LeftLowerArm", "LeftHand",
    # Right arm
    "RightShoulder", "RightUpperArm", "RightLowerArm", "RightHand",
]

UNITY_PARENTS: List[int] = [
    -1,             # Hips
    0,              # Spine <- Hips
    1,              # Chest <- Spine
    2,              # UpperChest <- Chest
    3,              # Neck <- UpperChest
    4,              # Head <- Neck
    # Left leg chain
    0,              # LeftUpperLeg <- Hips
    6,              # LeftLowerLeg <- LeftUpperLeg
    7,              # LeftFoot <- LeftLowerLeg
    8,              # LeftToes <- LeftFoot
    # Right leg chain
    0,              # RightUpperLeg <- Hips
    10,             # RightLowerLeg <- RightUpperLeg
    11,             # RightFoot <- RightLowerLeg
    12,             # RightToes <- RightFoot
    # Left arm chain
    3,              # LeftShoulder <- UpperChest
    14,             # LeftUpperArm <- LeftShoulder
    15,             # LeftLowerArm <- LeftUpperArm
    16,             # LeftHand <- LeftLowerArm
    # Right arm chain
    3,              # RightShoulder <- UpperChest
    18,             # RightUpperArm <- RightShoulder
    19,             # RightLowerArm <- RightUpperArm
    20,             # RightHand <- RightLowerArm
]

# Map Unity bones to SMPL indices (root uses R_root index 0; others use R_body by SMPL order)
# SMPL order reference used here:
# 0: pelvis(root), 1:left_hip,2:right_hip,3:spine1,4:left_knee,5:right_knee,6:spine2,7:left_ankle,8:right_ankle,
# 9:spine3,10:left_foot,11:right_foot,12:neck,13:left_collar,14:right_collar,15:head,16:left_shoulder,17:right_shoulder,
# 18:left_elbow,19:right_elbow,20:left_wrist,21:right_wrist,22:left_hand,23:right_hand
UNITY_TO_SMPL: Dict[str, tuple] = {
    "Hips": ("root", 0),
    "Spine": ("body", 3),
    "Chest": ("body", 6),
    "UpperChest": ("body", 9),
    "Neck": ("body", 12),
    "Head": ("body", 15),
    "LeftUpperLeg": ("body", 1),
    "LeftLowerLeg": ("body", 4),
    "LeftFoot": ("body", 7),
    "LeftToes": ("body", 10),  # closest available
    "RightUpperLeg": ("body", 2),
    "RightLowerLeg": ("body", 5),
    "RightFoot": ("body", 8),
    "RightToes": ("body", 11),
    "LeftShoulder": ("body", 13),
    "LeftUpperArm": ("body", 16),
    "LeftLowerArm": ("body", 18),
    "LeftHand": ("body", 20),
    "RightShoulder": ("body", 14),
    "RightUpperArm": ("body", 17),
    "RightLowerArm": ("body", 19),
    "RightHand": ("body", 21),
}


def ensure_blender():
    try:
        import bpy  # noqa: F401
        import mathutils  # noqa: F401
    except Exception as exc:
        raise SystemExit("This script must be run inside Blender: blender -b -P ... -- <args>") from exc


def create_armature(name: str = "UnityHumanoid_Armature"):
    import bpy

    # New scene base
    for obj in list(bpy.data.objects):
        obj.select_set(True)
    if bpy.data.objects:
        bpy.ops.object.delete()

    bpy.ops.object.armature_add(enter_editmode=True)
    arm_obj = bpy.context.active_object
    arm_obj.name = name
    arm = arm_obj.data
    arm.name = name + "Data"

    # The default bone is named "Bone"; we will repurpose it as pelvis
    edit_bones = arm.edit_bones
    pelvis = edit_bones[0]
    pelvis.name = UNITY_BONE_NAMES[0]  # Hips
    pelvis.head = (0.0, 0.0, 1.0)
    pelvis.tail = (0.0, 0.1, 1.0)

    # Heuristic T-pose lengths and directions (Z-up, Y-forward, X-right)
    # Build remaining bones
    def add_bone(bone_name: str, parent_name: str, head, tail):
        b = edit_bones.new(bone_name)
        b.head = head
        b.tail = tail
        b.use_connect = False
        if parent_name:
            parent_b = edit_bones[parent_name]
            b.parent = parent_b
            # Force continuous chain to avoid zero-length in Unity
            b.head = parent_b.tail
            b.use_connect = True
        return b

    # Predefine approximate heads/tails
    coords = {
        # Torso chain
        "Spine": ((0.0, 0.0, 1.0), (0.0, 0.0, 1.12)),
        "Chest": ((0.0, 0.0, 1.12), (0.0, 0.0, 1.24)),
        "UpperChest": ((0.0, 0.0, 1.24), (0.0, 0.0, 1.36)),
        "Neck": ((0.0, 0.0, 1.36), (0.0, 0.0, 1.46)),
        "Head": ((0.0, 0.0, 1.46), (0.0, 0.0, 1.60)),
        # Legs (X right, Z up)
        "LeftUpperLeg": ((0.08, 0.0, 1.0), (0.08, 0.0, 0.60)),
        "LeftLowerLeg": ((0.08, 0.0, 0.60), (0.08, 0.0, 0.12)),
        "LeftFoot": ((0.08, 0.0, 0.12), (0.12, 0.20, 0.08)),
        "LeftToes": ((0.12, 0.20, 0.08), (0.16, 0.28, 0.08)),
        "RightUpperLeg": ((-0.08, 0.0, 1.0), (-0.08, 0.0, 0.60)),
        "RightLowerLeg": ((-0.08, 0.0, 0.60), (-0.08, 0.0, 0.12)),
        "RightFoot": ((-0.08, 0.0, 0.12), (-0.12, 0.20, 0.08)),
        "RightToes": ((-0.12, 0.20, 0.08), (-0.16, 0.28, 0.08)),
        # Arms from UpperChest
        "LeftShoulder": ((0.02, 0.0, 1.36), (0.12, 0.0, 1.36)),
        "LeftUpperArm": ((0.12, 0.0, 1.36), (0.35, 0.0, 1.36)),
        "LeftLowerArm": ((0.35, 0.0, 1.36), (0.55, 0.0, 1.36)),
        "LeftHand": ((0.55, 0.0, 1.36), (0.65, 0.0, 1.36)),
        "RightShoulder": ((-0.02, 0.0, 1.36), (-0.12, 0.0, 1.36)),
        "RightUpperArm": ((-0.12, 0.0, 1.36), (-0.35, 0.0, 1.36)),
        "RightLowerArm": ((-0.35, 0.0, 1.36), (-0.55, 0.0, 1.36)),
        "RightHand": ((-0.55, 0.0, 1.36), (-0.65, 0.0, 1.36)),
    }

    # Create bones according to parents
    for i in range(1, len(UNITY_BONE_NAMES)):
        name = UNITY_BONE_NAMES[i]
        parent_idx = UNITY_PARENTS[i]
        parent_name = UNITY_BONE_NAMES[parent_idx] if parent_idx >= 0 else None
        head, tail = coords.get(name, ((0.0, 0.0, 1.0), (0.0, 0.0, 1.1)))
        add_bone(name, parent_name, head, tail)

    # Exit edit mode
    import bpy
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj


def mat3_to_quat(mat3: np.ndarray):
    from mathutils import Matrix
    M = Matrix(((float(mat3[0,0]), float(mat3[0,1]), float(mat3[0,2])),
                (float(mat3[1,0]), float(mat3[1,1]), float(mat3[1,2])),
                (float(mat3[2,0]), float(mat3[2,1]), float(mat3[2,2]))))
    return M.to_quaternion()


# Coordinate basis conversion: SMPL (x right, y up, z fwd)
#  -> Blender (x right, y fwd, z up)
# Use a proper rotation (not reflection): 90 degrees around +X axis
# C such that v_bl = C @ v_smpl; then R_bl = C @ R_smpl @ C^{-1}
C_BASIS = np.array([[1.0, 0.0,  0.0],
                    [0.0, 0.0, -1.0],
                    [0.0, 1.0,  0.0]], dtype=np.float64)
C_INV = C_BASIS.T

def smpl_to_blender_matrix(R: np.ndarray) -> np.ndarray:
    return C_BASIS @ R @ C_INV

# Optional root correction to match Unity Humanoid up-direction
R_FIX_ROOT = np.array([[1.0, 0.0, 0.0],
                       [0.0, -1.0, 0.0],
                       [0.0, 0.0, -1.0]], dtype=np.float64)  # Rx(pi)
R_FIX_YAW = np.array([[-1.0, 0.0, 0.0],
                      [ 0.0, 1.0, 0.0],
                      [ 0.0, 0.0, -1.0]], dtype=np.float64)  # Rz(pi) in Unity -> equivalent yaw 180


def bake_animation(arm_obj, R_root: np.ndarray, R_body: np.ndarray, camera: np.ndarray, frame_idx: np.ndarray, fps: int, with_root_motion: bool):
    import bpy
    bpy.context.scene.render.fps = int(fps)
    # Ensure action exists so FBX exporter finds animation data
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    action = bpy.data.actions.new(name="Take 001")
    arm_obj.animation_data.action = action
    # Normalize frame indices to start at 1
    frame_idx = np.asarray(frame_idx)
    sorted_order = np.argsort(frame_idx)
    R_root = R_root[sorted_order]
    R_body = R_body[sorted_order]
    camera = camera[sorted_order]
    frame_idx = frame_idx[sorted_order]
    frame_idx = frame_idx - frame_idx.min() + 1

    pose_bones = arm_obj.pose.bones
    # Ensure quaternion mode
    for name in UNITY_BONE_NAMES:
        if name in pose_bones:
            pose_bones[name].rotation_mode = 'QUATERNION'

    # Set explicit frame range
    bpy.context.scene.frame_start = int(frame_idx.min()) if frame_idx.size > 0 else 1
    for f, (Mr, Mb, cam) in enumerate(zip(R_root, R_body, camera)):
        frame = int(frame_idx[f])
        bpy.context.scene.frame_set(frame)

        # Root rotation (convert SMPL -> Blender basis)
        root_pb = pose_bones[UNITY_BONE_NAMES[0]]  # Hips
        Mr_bl = smpl_to_blender_matrix(Mr)
        # Apply 180deg X flip to root to align up-direction for Unity Humanoid
        Mr_bl = R_FIX_ROOT @ Mr_bl
        # Align facing forward (yaw 180) if needed
        Mr_bl = R_FIX_YAW @ Mr_bl
        q_root = mat3_to_quat(Mr_bl)
        root_pb.rotation_quaternion = q_root
        root_pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)

        # Optional root motion as pelvis location in armature space
        if with_root_motion:
            # PHALP uses camera tz scaled (z/200). We assume NPZ already raw camera.
            tx, ty, tz = float(cam[0]), float(cam[1]), float(cam[2] / 200.0)
            # Map to Blender axes (Z-up, Y forward). Original camera is wrt image; empirically use (X=tx, Y=ty, Z=tz)
            root_pb.location = (tx, ty, tz)
            root_pb.keyframe_insert(data_path='location', frame=frame)

        # Body joints
        for j in range(1, len(UNITY_BONE_NAMES)):
            name = UNITY_BONE_NAMES[j]
            if name not in pose_bones:
                continue
            src = UNITY_TO_SMPL.get(name)
            if src is None:
                continue
            src_type, idx = src
            if src_type == "root":
                M_src = Mr
            else:
                # idx maps directly to SMPL body index
                M_src = Mb[idx-1] if idx > 0 else Mb[0]
            Mj_bl = smpl_to_blender_matrix(M_src)
            # Fix feet/toes pointing backward by yaw 180 on local
            if name in ("LeftFoot", "RightFoot", "LeftToes", "RightToes"):
                Mj_bl = R_FIX_YAW @ Mj_bl
            q = mat3_to_quat(Mj_bl)
            pb = pose_bones[name]
            pb.rotation_quaternion = q
            pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)

    bpy.context.scene.frame_end = int(frame_idx.max())
    # Insert dummy object-level keys to guarantee curves exist (helps Unity detect animation)
    arm_obj.location = (0.0, 0.0, 0.0)
    arm_obj.keyframe_insert(data_path='location', frame=int(bpy.context.scene.frame_start))
    arm_obj.keyframe_insert(data_path='location', frame=int(bpy.context.scene.frame_end))
    arm_obj.scale = (1.0, 1.0, 1.0)
    arm_obj.keyframe_insert(data_path='scale', frame=int(bpy.context.scene.frame_start))
    arm_obj.keyframe_insert(data_path='scale', frame=int(bpy.context.scene.frame_end))


def export_fbx(arm_obj, out_path: str):
    import bpy
    # Ensure action in NLA so FBX exporter bakes it explicitly
    if arm_obj.animation_data is not None:
        if arm_obj.animation_data.nla_tracks is None:
            arm_obj.animation_data_create()
        track = arm_obj.animation_data.nla_tracks.new()
        track.name = "Take 001"
        start_f = int(bpy.context.scene.frame_start)
        strip = track.strips.new(name="Take 001", start=start_f, action=arm_obj.animation_data.action)
        strip.frame_start = float(bpy.context.scene.frame_start)
        strip.frame_end = float(bpy.context.scene.frame_end)

    # Select only armature
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    # Export settings tailored for Unity Humanoid
    bpy.ops.export_scene.fbx(
        filepath=out_path,
        use_selection=True,
        apply_unit_scale=True,
        bake_space_transform=True,
        object_types={'ARMATURE'},
        use_armature_deform_only=True,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
        bake_anim_use_nla_strips=True,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        axis_forward='-Z', axis_up='Y'
    )


def main_blender(args):
    ensure_blender()
    data = load_npz(args.npz)
    R_root = data['R_root']
    R_body = data['R_body']
    camera = data['camera']
    frame_idx = data['frame_idx']
    fps_npz = int(data['fps'][0]) if 'fps' in data and data['fps'].size > 0 else args.fps

    arm_obj = create_armature()
    bake_animation(arm_obj, R_root, R_body, camera, frame_idx, fps_npz, args.with_root_motion)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    export_fbx(arm_obj, args.out)
    print(f"Exported FBX: {args.out}")
    n_frames = int(R_root.shape[0])
    print(f"[blender] baked frames={n_frames} frame_range=[{int(frame_idx.min())}, {int(frame_idx.max())}] fps={fps_npz}")


if __name__ == "__main__":
    # Blender passes args after '--'. Find that split.
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    args = parse_args(argv)
    main_blender(args)


