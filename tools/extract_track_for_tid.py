#!/usr/bin/env python3
"""
Extract a single track (by tid) from a PHALP/4D-Humans results .pkl
into a compact NPZ for Blender consumption.

The NPZ contains:
  - frame_idx: (N,) int array of frame indices (if available) or sequential 0..N-1
  - R_root: (N, 3, 3) rotation matrices for SMPL global_orient
  - R_body: (N, 23, 3, 3) rotation matrices for SMPL body_pose
  - camera: (N, 3) camera translation [tx, ty, tz] if available else zeros
  - fps: scalar (saved as metadata key)

Usage:
  python tools/extract_track_for_tid.py --pkl outputs/results/demo_7111.pkl --tid 1 --out outputs/results/demo_7111_tid1.npz --fps 30
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Tuple

import numpy as np


def safe_load_pkl(pkl_path: str) -> Dict[str, Any]:
    try:
        import joblib  # preferred
        return joblib.load(pkl_path)
    except Exception:
        import pickle
        with open(pkl_path, "rb") as f:
            return pickle.load(f)


def natural_frame_sort_keys(keys: List[str], frame_data: Dict[str, Any]) -> List[str]:
    # Prefer 'time' field if present and consistent across frames
    if all(isinstance(frame_data[k], dict) and "time" in frame_data[k] for k in keys):
        return sorted(keys, key=lambda k: int(frame_data[k]["time"]))
    # Fallback: numeric parse of basename
    def _key(k: str) -> Tuple:
        import re
        m = re.search(r"(\d+)", k)
        return (int(m.group(1)) if m else 0, k)
    return sorted(keys, key=_key)


def to_rotation_matrix_array(x: Any, expected: Tuple[int, ...]) -> np.ndarray:
    arr = np.array(x)
    if arr.size == np.prod(expected):
        return arr.reshape(expected)
    # Try to infer 3x3 matrices from axis-angle (N, 3) if encountered (rare in PHALP dumps)
    if arr.ndim == 2 and arr.shape[-1] == 3:
        import numpy as _np
        def axis_angle_to_matrix(v):
            theta = _np.linalg.norm(v)
            if theta < 1e-8:
                return _np.eye(3)
            k = v / theta
            K = _np.array([[0, -k[2], k[1]],[k[2], 0, -k[0]],[-k[1], k[0], 0]])
            R = _np.eye(3) + _np.sin(theta) * K + (1 - _np.cos(theta)) * (K @ K)
            return R
        mats = _np.stack([axis_angle_to_matrix(v) for v in arr], axis=0)
        if mats.shape == expected:
            return mats
    raise ValueError(f"Unexpected rotation data shape {arr.shape}, expected {expected}")


def extract_track(data: Dict[str, Any], target_tid: int) -> Dict[str, np.ndarray]:
    frame_keys = list(data.keys())
    frame_keys = natural_frame_sort_keys(frame_keys, data)

    R_root_list: List[np.ndarray] = []
    R_body_list: List[np.ndarray] = []
    cam_list: List[np.ndarray] = []
    frame_idx_list: List[int] = []
    betas_list: List[np.ndarray] = []
    
    # New: additional data for motion analysis
    joints_3d_list: List[np.ndarray] = []
    bbox_list: List[np.ndarray] = []
    center_list: List[np.ndarray] = []
    scale_list: List[float] = []
    img_size_list: List[np.ndarray] = []

    for k in frame_keys:
        fr = data[k]
        if not isinstance(fr, dict):
            continue
        tids = fr.get("tracked_ids") or fr.get("tid") or []
        try:
            tids = [int(x) for x in tids]
        except Exception:
            continue
        matches = [i for i, t in enumerate(tids) if t == int(target_tid)]
        if not matches:
            continue
        idx = matches[0]

        smpl_list = fr.get("smpl")
        if not smpl_list or idx >= len(smpl_list):
            continue
        smpl = smpl_list[idx]
        if smpl is None or smpl == -1:
            continue

        try:
            R_root = to_rotation_matrix_array(smpl["global_orient"], (3, 3))
            R_body = to_rotation_matrix_array(smpl["body_pose"], (23, 3, 3))
            # Extract betas (body shape parameters)
            betas = np.array(smpl.get("betas", np.zeros(10)), dtype=np.float32)
        except Exception as e:
            # Skip frames with malformed pose
            continue

        camera_list = fr.get("camera")
        if camera_list and idx < len(camera_list):
            cam = np.array(camera_list[idx], dtype=np.float32).reshape(3)
        else:
            cam = np.zeros((3,), dtype=np.float32)

        frame_idx = int(fr.get("time", len(frame_idx_list)))
        
        # Extract additional data for motion analysis
        joints_3d_list_fr = fr.get("3d_joints")
        if joints_3d_list_fr and idx < len(joints_3d_list_fr):
            joints_3d = np.array(joints_3d_list_fr[idx], dtype=np.float32)
        else:
            joints_3d = np.zeros((45, 3), dtype=np.float32)
        
        bbox_list_fr = fr.get("bbox")
        if bbox_list_fr and idx < len(bbox_list_fr):
            bbox = np.array(bbox_list_fr[idx], dtype=np.float32)
        else:
            bbox = np.zeros(4, dtype=np.float32)
        
        center_list_fr = fr.get("center")
        if center_list_fr and idx < len(center_list_fr):
            center = np.array(center_list_fr[idx], dtype=np.float32)
        else:
            center = np.zeros(2, dtype=np.float32)
        
        scale_list_fr = fr.get("scale")
        if scale_list_fr and idx < len(scale_list_fr):
            scale = float(scale_list_fr[idx])
        else:
            scale = 0.0
        
        size_list_fr = fr.get("size")
        if size_list_fr and len(size_list_fr) > 0:
            img_size = np.array(size_list_fr[0], dtype=np.float32)
        else:
            img_size = np.array([1920, 1080], dtype=np.float32)

        R_root_list.append(R_root.astype(np.float32))
        R_body_list.append(R_body.astype(np.float32))
        cam_list.append(cam)
        frame_idx_list.append(frame_idx)
        betas_list.append(betas)
        joints_3d_list.append(joints_3d)
        bbox_list.append(bbox)
        center_list.append(center)
        scale_list.append(scale)
        img_size_list.append(img_size)

    if not R_root_list:
        raise SystemExit("No valid frames extracted for the specified tid.")

    order = np.argsort(np.array(frame_idx_list))
    R_root_arr = np.stack([R_root_list[i] for i in order], axis=0)
    R_body_arr = np.stack([R_body_list[i] for i in order], axis=0)
    cam_arr = np.stack([cam_list[i] for i in order], axis=0)
    frame_idx_arr = np.array([frame_idx_list[i] for i in order], dtype=np.int32)
    betas_arr = np.stack([betas_list[i] for i in order], axis=0)
    joints_3d_arr = np.stack([joints_3d_list[i] for i in order], axis=0)
    bbox_arr = np.stack([bbox_list[i] for i in order], axis=0)
    center_arr = np.stack([center_list[i] for i in order], axis=0)
    scale_arr = np.array([scale_list[i] for i in order], dtype=np.float32)
    img_size_arr = np.stack([img_size_list[i] for i in order], axis=0)

    return {
        "R_root": R_root_arr,
        "R_body": R_body_arr,
        "camera": cam_arr,
        "frame_idx": frame_idx_arr,
        "betas": betas_arr,
        "3d_joints": joints_3d_arr,
        "bbox": bbox_arr,
        "center": center_arr,
        "scale": scale_arr,
        "img_size": img_size_arr,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkl", required=True)
    ap.add_argument("--tid", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    data = safe_load_pkl(args.pkl)
    track = extract_track(data, args.tid)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    np.savez_compressed(
        args.out,
        R_root=track["R_root"],
        R_body=track["R_body"],
        camera=track["camera"],
        frame_idx=track["frame_idx"],
        betas=track["betas"],
        fps=np.array([args.fps], dtype=np.int32),
        **{"3d_joints": track["3d_joints"],
           "bbox": track["bbox"],
           "center": track["center"],
           "scale": track["scale"],
           "img_size": track["img_size"]}
    )
    n_frames = int(track["R_root"].shape[0])
    f0 = int(track["frame_idx"][0])
    f1 = int(track["frame_idx"][-1])
    print(f"Saved NPZ: {args.out}")
    print(f"[extract] tid={args.tid} frames={n_frames} frame_range=[{f0}, {f1}] fps={args.fps}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)


