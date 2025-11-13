#!/usr/bin/env python3
"""
Adapt 4D-Humans NPZ (R_root/R_body) to SmoothNet, run temporal smoothing,
and write back a smoothed NPZ. If SmoothNet is unavailable, falls back to
headless lightweight smoothing (moving-average on 6D rotation and EMA on root).

Usage (SmoothNet env):
  export PYTHONPATH=$HOME/SmoothNet:$HOME/SmoothNet/lib:$PYTHONPATH
  python tools/adapt_smoothnet.py \
    --npz /path/in.npz \
    --ckpt /path/smoothnet.pth \
    --out /path/out_smoothed.npz \
    --rep 6d --win 9 --ema 0.2

Notes:
  - Input NPZ must contain: R_root (T,3,3), R_body (T,23,3,3), frame_idx (T,)
    Optional: camera (T,3), fps (scalar)
  - Output NPZ preserves the same fields with smoothed rotations/camera
  - This script does not require SmoothNet to exist; if import or ckpt fails,
    it performs a safe lightweight smoothing.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Optional, Tuple

import numpy as np


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz', required=True, help='Input NPZ with R_root/R_body')
    ap.add_argument('--ckpt', default='', help='SmoothNet checkpoint (optional)')
    ap.add_argument('--out', required=True, help='Output NPZ path')
    ap.add_argument('--rep', default='6d', choices=['6d'], help='Rotation representation for smoothing')
    ap.add_argument('--win', type=int, default=9, help='Temporal window for smoothing (odd)')
    ap.add_argument('--ema', type=float, default=0.2, help='EMA factor for camera smoothing (0..1)')
    ap.add_argument('--strength', type=float, default=1.0, help='Blend 0..1 between original (0) and smoothed (1) rotations')
    return ap.parse_args()


def load_npz(path: str) -> dict:
    data = np.load(path, allow_pickle=True)
    needed = ['R_root', 'R_body', 'frame_idx']
    for k in needed:
        if k not in data:
            raise SystemExit(f'Missing key in NPZ: {k}')
    return {k: data[k] for k in data.files}


def rotmat_to_6d(R: np.ndarray) -> np.ndarray:
    """(T,3,3) -> (T,6) using first two rows (row-major).

    We keep consistency with Blender/mathutils which expects row-major when
    building matrices from nested tuples. Using rows here guarantees the
    round-trip rotmat->6d->rotmat equals identity.
    """
    return R[..., :2, :].reshape(R.shape[:-2] + (6,))


def _normalize(v: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.clip(n, eps, None)


def rot6d_to_rotmat(x: np.ndarray) -> np.ndarray:
    """(T,6) -> (T,3,3) via Gram-Schmidt (rows).

    Interprets the 6D as the first two ROWS, then recovers the third row by a
    right-handed cross product. Returns a row-major rotation matrix.
    """
    r1 = _normalize(x[..., 0:3])
    r2 = x[..., 3:6]
    r2 = _normalize(r2 - (r1 * r2).sum(-1, keepdims=True) * r1)
    r3 = np.cross(r1, r2)
    return np.stack([r1, r2, r3], axis=-2)  # (...,3,3) as rows


def pack_rot_6d(R_root: np.ndarray, R_body: np.ndarray) -> np.ndarray:
    """R_root (T,3,3), R_body (T,23,3,3) -> X (1,T,24*6)."""
    T = R_root.shape[0]
    root6 = rotmat_to_6d(R_root)                 # (T,6)
    body6 = rotmat_to_6d(R_body.reshape(T*23,3,3)).reshape(T,23,6)
    all6 = np.concatenate([root6[:,None,:], body6], axis=1)  # (T,24,6)
    X = all6.reshape(1, T, 24*6)
    return X


def unpack_rot_6d(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """X (1,T,24*6) -> R_root(T,3,3), R_body(T,23,3,3)."""
    assert X.ndim == 3 and X.shape[0] == 1, 'Expected (1,T,D)'
    T = X.shape[1]
    all6 = X.reshape(T, 24, 6)
    root6 = all6[:, 0, :]
    body6 = all6[:, 1:, :]
    R_root = rot6d_to_rotmat(root6)
    R_body = rot6d_to_rotmat(body6.reshape(T*23, 6)).reshape(T, 23, 3, 3)
    return R_root, R_body


def smooth_moving_average(X: np.ndarray, win: int) -> np.ndarray:
    """Centered moving average with 'same' length output along time (axis=1).

    Keeps the temporal length identical to the input by padding and using a
    prefix-sum trick with a leading zero to avoid the classic off-by-one.
    """
    if win < 3 or win % 2 == 0:
        return X
    pad = win // 2
    Xpad = np.pad(X, ((0, 0), (pad, pad), (0, 0)), mode='edge')
    cumsum = np.cumsum(Xpad, axis=1)
    # prepend a zero-frame so windowed differences yield length == T + 2*pad - win + 1 == T
    cumsum = np.concatenate([np.zeros_like(Xpad[:, :1, :]), cumsum], axis=1)
    Y = (cumsum[:, win:, :] - cumsum[:, :-win, :]) / float(win)
    return Y


def ema_smooth(C: np.ndarray, alpha: float) -> np.ndarray:
    if not (0.0 < alpha < 1.0):
        return C
    Y = np.empty_like(C)
    Y[0] = C[0]
    for t in range(1, C.shape[0]):
        Y[t] = alpha * C[t] + (1.0 - alpha) * Y[t-1]
    return Y


def try_import_smoothnet():
    """Try to import SmoothNet Model and builder from common paths."""
    candidates = [
        ('lib.models.smoothnet', 'SmoothNet'),
        ('models.smoothnet', 'SmoothNet'),
        ('smoothnet', 'SmoothNet'),
    ]
    for mod, cls in candidates:
        try:
            m = __import__(mod, fromlist=[cls])
            Model = getattr(m, cls)
            return Model
        except Exception:
            continue
    return None


def run_smoothnet(X: np.ndarray, ckpt_path: str, win: int) -> Tuple[Optional[np.ndarray], bool, str]:
    Model = try_import_smoothnet()
    if Model is None or not ckpt_path or not os.path.isfile(ckpt_path):
        return None, False, 'unavailable'
    try:
        import torch
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        # SmoothNet constructor in your repo requires window_size/output_size only
        # output_size must be <= window_size; we use the same value 'win'
        # Match training config in your checkpoint (res_hidden_size=128)
        model = Model(window_size=int(win), output_size=int(win), res_hidden_size=128)
        ckpt = torch.load(ckpt_path, map_location='cpu')
        # Generic ckpt loading (key names may differ across forks)
        state = ckpt.get('state_dict', ckpt)
        model.load_state_dict({k.replace('model.', ''): v for k,v in state.items()}, strict=False)
        model.to(device)
        model.eval()
        with torch.no_grad():
            # Sliding-window inference: model expects temporal length == window_size
            T, D = int(X.shape[1]), int(X.shape[2])
            if T < win:
                # pad to win using edge values
                pad = win - T
                Xp = np.pad(X, ((0,0),(0,pad),(0,0)), mode='edge')
                Tpad = win
            else:
                Xp = X
                Tpad = T

            Y_sum = np.zeros((Tpad, D), dtype=np.float32)
            cnt = np.zeros((Tpad, 1), dtype=np.float32)
            N = Tpad - win + 1
            x_tensor_full = torch.from_numpy(Xp).float().to(device)  # (1,T,D)
            e1 = e2 = None
            for i in range(N):
                xw = x_tensor_full[:, i:i+win, :]  # (1,win,D)
                try:
                    yw = model(xw)  # try (1,win,D)
                except Exception as _e1:
                    e1 = _e1
                    try:
                        yw = model(xw.permute(0,2,1))  # (1,D,win)
                        yw = yw.permute(0,2,1)        # back to (1,win,D)
                    except Exception as _e2:
                        e2 = _e2
                        raise RuntimeError(f"SmoothNet forward failed: {e1} | alt: {e2}")
                ywn = yw.detach().cpu().numpy()[0]  # (win,D)
                Y_sum[i:i+win] += ywn
                cnt[i:i+win] += 1.0
            Y_full = Y_sum / np.clip(cnt, 1.0, None)
            Y = Y_full[:T].reshape(1, T, D)
        return Y, True, str(device)
    except Exception as e:
        print(f"[smooth] SmoothNet error: {e}")
        return None, False, 'error'


def _mean_angle_deg(Ra: np.ndarray, Rb: np.ndarray) -> float:
    """Mean geodesic angle between rotations Ra and Rb in degrees.
    Ra/Rb: (...,3,3)
    """
    from numpy import swapaxes
    D = Ra @ swapaxes(Rb, -1, -2)
    tr = np.clip((D[..., 0, 0] + D[..., 1, 1] + D[..., 2, 2] - 1.0) / 2.0, -1.0, 1.0)
    ang = np.degrees(np.arccos(tr))
    return float(np.mean(ang))


def _stack24(R_root: np.ndarray, R_body: np.ndarray) -> np.ndarray:
    # (T,3,3), (T,23,3,3) -> (T,24,3,3)
    return np.concatenate([R_root[:, None, :, :], R_body], axis=1)


def _velocity_mse(R: np.ndarray) -> float:
    """Mean squared geodesic velocity per joint."""
    D = R[1:] @ np.transpose(R[:-1], axes=(0, 1, 3, 2))
    tr = np.clip((D[..., 0, 0] + D[..., 1, 1] + D[..., 2, 2] - 1.0) / 2.0, -1.0, 1.0)
    ang = np.arccos(tr)  # radians
    return float(np.mean(ang ** 2))


def main():
    args = parse_args()
    data = load_npz(args.npz)

    R_root = data['R_root'].astype(np.float32)
    R_body = data['R_body'].astype(np.float32)
    frame_idx = data['frame_idx'].astype(np.int32)
    camera = data.get('camera', None)
    fps = data.get('fps', None)
    betas = data.get('betas', None)  # Preserve body shape parameters

    # Pack to 6D
    X = pack_rot_6d(R_root, R_body)  # (1,T,D)

    # Try SmoothNet, else fallback
    Y, used_model, dev = run_smoothnet(X, args.ckpt, args.win)
    if Y is None:
        Y = smooth_moving_average(X, args.win)

    # Blend with original to control smoothing strength
    s = float(max(0.0, min(1.0, args.strength)))
    Z = (1.0 - s) * X + s * Y

    # Unpack back to rotation matrices
    R_root_s, R_body_s = unpack_rot_6d(Z)

    # Ensure auxiliary arrays match temporal length
    T = R_root_s.shape[0]

    # Smooth root translation (camera) by EMA if provided
    if camera is not None:
        camera_s = ema_smooth(camera.astype(np.float32), args.ema)
        camera_s = camera_s[:T]
    else:
        camera_s = None

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out_dict = {
        'R_root': R_root_s,
        'R_body': R_body_s,
        'camera': camera_s if camera_s is not None else camera,
        'frame_idx': frame_idx[:T],
        'fps': fps if fps is not None else np.array([30], dtype=np.int32),
    }
    # Preserve betas if present
    if betas is not None:
        out_dict['betas'] = betas[:T]
    
    # Preserve additional fields for motion analysis (pass-through, no smoothing)
    extra_fields = ['3d_joints', 'bbox', 'center', 'scale', 'img_size']
    for field in extra_fields:
        if field in data:
            out_dict[field] = data[field][:T]
    
    np.savez_compressed(args.out, **out_dict)
    # Report smoothing statistics (before vs after)
    R0 = _stack24(R_root, R_body)
    Rs = _stack24(R_root_s, R_body_s)
    ang_mean = _mean_angle_deg(Rs, R0)
    mse0 = _velocity_mse(R0)
    mseS = _velocity_mse(Rs)
    red = 100.0 * (1.0 - (mseS / (mse0 + 1e-8)))
    used = f"SmoothNet:{used_model}({dev})" if used_model else "fallback:moving_average"
    print(f"[smooth] engine={used} win={args.win} strength={s} ema={args.ema}")
    print(f"[smooth] mean_angle_deg={ang_mean:.4f}  vel_mse_reduction={red:.2f}%")
    print(f"[done] saved: {args.out}")


if __name__ == '__main__':
    main()


