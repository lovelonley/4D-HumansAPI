#!/usr/bin/env python3
"""
Use the installed SMPL-X Blender addon to create a standard SMPL-X armature,
apply SMPL pose rotations from an NPZ (R_root, R_body), and export to FBX for
Unity Humanoid. This avoids custom armature orientation issues.

Run:
  blender -b -P tools/blender/smplx_npz_to_fbx.py -- \
    --npz /abs/path/demo_7111_tid1.npz \
    --out /abs/path/demo_7111_tid1_smplx.fbx \
    --fps 30
"""

from __future__ import annotations

import argparse
import sys
import os
from typing import Dict, List

import numpy as np


def parse_args(argv: List[str]):
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--with-root-motion", action="store_true")
    ap.add_argument("--cam-scale", type=float, default=1.0, help="Scale for camera translation (meters per unit)")
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


# SMPL indices (same as earlier mapping)
SMPL_NAMES = [
    "pelvis",          # 0 (root in SMPL)
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


# Map from our SMPL names to SMPL-X addon armature bone names
SMPL_TO_SMPLX = {
    "pelvis": "pelvis",
    "spine1": "spine1",
    "spine2": "spine2",
    "spine3": "spine3",
    "neck": "neck",
    "head": "head",
    "left_hip": "left_hip",
    "left_knee": "left_knee",
    "left_ankle": "left_ankle",
    "left_foot": "left_foot",
    "right_hip": "right_hip",
    "right_knee": "right_knee",
    "right_ankle": "right_ankle",
    "right_foot": "right_foot",
    "left_collar": "left_collar",
    "left_shoulder": "left_shoulder",
    "left_elbow": "left_elbow",
    "left_wrist": "left_wrist",
    "right_collar": "right_collar",
    "right_shoulder": "right_shoulder",
    "right_elbow": "right_elbow",
    "right_wrist": "right_wrist",
}


def mat3_to_quat(M: np.ndarray):
    from mathutils import Matrix
    m = Matrix(((float(M[0,0]), float(M[0,1]), float(M[0,2])),
                (float(M[1,0]), float(M[1,1]), float(M[1,2])),
                (float(M[2,0]), float(M[2,1]), float(M[2,2]))))
    return m.to_quaternion()


# Root flip to resolve upside-down (rotate 180 degrees around X)
R_FLIP_X = np.array([[1.0, 0.0, 0.0],
                     [0.0, -1.0, 0.0],
                     [0.0, 0.0, -1.0]], dtype=np.float64)


def create_smplx_armature() -> "bpy.types.Object":
    import bpy
    # Clean scene
    for obj in list(bpy.data.objects):
        obj.select_set(True)
    if bpy.data.objects:
        bpy.ops.object.delete()

    # Add SMPL-X character via addon (defaults: female, relaxed hands)
    bpy.ops.scene.smplx_add_gender()
    arm = None
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            arm = obj
            break
    if arm is None:
        raise RuntimeError("SMPL-X armature not created")
    return arm


def bake_animation_with_smplx(arm_obj, R_root: np.ndarray, R_body: np.ndarray, frame_idx: np.ndarray, fps: int, camera: np.ndarray | None = None, cam_scale: float = 1.0, with_root_motion: bool = False):
    import bpy
    bpy.context.scene.render.fps = int(fps)

    # Sort frames by index and normalize to start at 1
    order = np.argsort(frame_idx)
    R_root = R_root[order]
    R_body = R_body[order]
    frame_idx = frame_idx[order]
    frame_idx = frame_idx - frame_idx.min() + 1

    # Pose bones rotation mode
    for b in arm_obj.pose.bones:
        b.rotation_mode = 'QUATERNION'

    # Bone mapping
    pbones = arm_obj.pose.bones
    for f in range(frame_idx.shape[0]):
        frame = int(frame_idx[f])
        bpy.context.scene.frame_set(frame)

        # Root (pelvis)
        if 'pelvis' in pbones:
            Mr = R_root[f]
            # Note: R_FLIP_X removed - it caused upside-down skeleton in Unity
            # Mr = R_FLIP_X @ Mr
            q = mat3_to_quat(Mr)
            pb = pbones['pelvis']
            pb.rotation_quaternion = q
            pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            if with_root_motion and camera is not None:
                cam = camera[order][f] if camera.shape[0] == order.shape[0] else camera[f]
                tx, ty, tz = float(cam[0]), float(cam[1]), float(cam[2])
                # OpenCV (x right, y down, z forward) -> Blender (x right, y forward, z up)
                x_bl = tx * cam_scale
                y_bl = tz * cam_scale
                z_bl = (-ty) * cam_scale
                pb.location = (x_bl, y_bl, z_bl)
                pb.keyframe_insert(data_path='location', frame=frame)

        # Others
        for smpl_name, smplx_name in SMPL_TO_SMPLX.items():
            if smpl_name == 'pelvis':
                continue
            if smplx_name not in pbones:
                continue
            # index lookup
            try:
                idx = SMPL_NAMES.index(smpl_name)
            except ValueError:
                continue
            if idx == 0:
                M = R_root[f]
            else:
                M = R_body[f, idx-1]
            q = mat3_to_quat(M)
            pb = pbones[smplx_name]
            pb.rotation_quaternion = q
            pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)

    bpy.context.scene.frame_start = int(frame_idx.min())
    bpy.context.scene.frame_end = int(frame_idx.max())

    # Create action to be safe
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()
    if arm_obj.animation_data.action is None:
        import bpy
        arm_obj.animation_data.action = bpy.data.actions.new(name='Take 001')


def export_fbx_via_addon(arm_obj, out_path: str):
    import bpy
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    try:
        bpy.ops.object.smplx_export_fbx(filepath=out_path, target_format='UNITY')
        print(f"[export] smplx_export_fbx -> {out_path}")
    except Exception as e:
        print('[export] smplx_export_fbx failed, fallback:', e)
        bpy.ops.export_scene.fbx(
            filepath=out_path,
            use_selection=True,
            apply_unit_scale=True,
            bake_space_transform=True,
            object_types={'ARMATURE'},
            add_leaf_bones=False,
            bake_anim=True,
            bake_anim_force_startend_keying=True,
            bake_anim_step=1.0,
            bake_anim_simplify_factor=0.0,
            axis_forward='-Z', axis_up='Y'
        )
        print(f"[export] fallback FBX -> {out_path}")


def main_blender(args):
    ensure_blender()
    data = load_npz(args.npz)
    R_root = data['R_root']
    R_body = data['R_body']
    frame_idx = data['frame_idx']
    fps = int(data['fps'][0]) if 'fps' in data and data['fps'].size > 0 else args.fps
    camera = data['camera'] if 'camera' in data else None

    arm_obj = create_smplx_armature()
    bake_animation_with_smplx(arm_obj, R_root, R_body, frame_idx, fps, camera=camera, cam_scale=args.cam_scale, with_root_motion=args.with_root_motion)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    export_fbx_via_addon(arm_obj, args.out)
    print(f"Exported FBX: {args.out}")


if __name__ == '__main__':
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    args = parse_args(argv)
    main_blender(args)


