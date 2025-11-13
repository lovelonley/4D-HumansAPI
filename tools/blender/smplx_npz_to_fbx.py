#!/usr/bin/env python3
"""
Convert NPZ (rotation matrices) to FBX using official SMPL-X Blender addon.

This script uses the original SMPL-X addon from Max Planck Institute.
It converts our rotation matrix format to AMASS format and uses the addon's
built-in animation import functionality.

Requirements:
- Blender 3.6+
- Official SMPL-X Blender addon installed
  Download from: https://smpl-x.is.tue.mpg.de/

Usage:
  blender -b -P tools/blender/smplx_npz_to_fbx.py -- \
    --npz path/to/data.npz \
    --out path/to/output.fbx \
    --fps 30 \
    --gender female

NPZ Format (input):
  - R_root: (T, 3, 3) - Root rotation matrices
  - R_body: (T, 23, 3, 3) - Body joint rotation matrices  
  - frame_idx: (T,) - Frame indices
  - fps: scalar - Frame rate
  - camera: (T, 3) - Optional camera translation
  - betas: (T, 10) or (10,) - Optional shape parameters

The script will:
1. Convert rotation matrices to Rodrigues vectors (AMASS format)
2. Create temporary NPZ in AMASS format
3. Use addon's smplx_add_animation to load animation
4. Export to FBX using addon's smplx_export_fbx
"""

import sys
import os
import argparse
import numpy as np
from pathlib import Path


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Convert NPZ to FBX using SMPL-X addon")
    ap.add_argument("--npz", required=True, help="Input NPZ file with rotation matrices")
    ap.add_argument("--out", required=True, help="Output FBX file path")
    ap.add_argument("--fps", type=int, default=30, help="Frame rate (default: 30)")
    ap.add_argument("--gender", default="female", choices=["female", "male", "neutral"], 
                    help="Body gender (default: female)")
    ap.add_argument("--target-format", default="UNITY", choices=["UNITY", "UNREAL"],
                    help="Target game engine format (default: UNITY)")
    return ap.parse_args(argv)


def ensure_blender():
    """Ensure we're running inside Blender."""
    try:
        import bpy  # noqa: F401
    except Exception as exc:
        raise SystemExit("Run inside Blender: blender -b -P ... -- <args>") from exc


def rotmat_to_rodrigues(R: np.ndarray) -> np.ndarray:
    """
    Convert 3x3 rotation matrix to Rodrigues vector (axis-angle).
    
    Based on cv2.Rodrigues formula without scipy dependency.
    """
    theta = np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    
    if theta < 1e-6:
        # Small angle, return zero vector
        return np.zeros(3, dtype=np.float64)
    
    # Compute rotation axis
    r = np.array([
        R[2, 1] - R[1, 2],
        R[0, 2] - R[2, 0],
        R[1, 0] - R[0, 1]
    ], dtype=np.float64)
    
    axis = r / (2 * np.sin(theta))
    
    # Rodrigues vector = axis * angle
    rodrigues = axis * theta
    return rodrigues.astype(np.float64)


def convert_to_amass_format(npz_path: str, output_path: str, gender: str, fps: int):
    """
    Convert our NPZ format (rotation matrices) to AMASS format (Rodrigues vectors).
    
    AMASS format requirements:
    - trans: (T, 3) - Translation in meters
    - gender: str or bytes - "female", "male", or "neutral"  
    - mocap_framerate or mocap_frame_rate: int - Frame rate
    - betas: (10,) or (300,) - Shape parameters
    - poses: (T, 165) - Full body pose in Rodrigues (55 joints * 3)
    
    Our format:
    - R_root: (T, 3, 3) - Root rotation matrices (Y-down coordinate system)
    - R_body: (T, 23, 3, 3) - Body joint rotation matrices
    - frame_idx: (T,) - Frame indices
    - camera: (T, 3) - Optional camera translation
    - betas: (T, 10) or (10,) - Optional shape parameters
    """
    print(f"[convert] Loading NPZ: {npz_path}")
    data = np.load(npz_path)
    
    R_root = data['R_root']  # (T, 3, 3)
    R_body = data['R_body']  # (T, 23, 3, 3)
    frame_idx = data['frame_idx']
    
    T = R_root.shape[0]
    print(f"[convert] Frames: {T}, FPS: {fps}, Gender: {gender}")
    
    # Get camera translation (default to zeros if not available)
    if 'camera' in data and data['camera'].size > 0:
        trans = data['camera'].copy()  # (T, 3)
    else:
        trans = np.zeros((T, 3), dtype=np.float64)
    
    # Get betas (default to zeros if not available)
    if 'betas' in data and data['betas'].size > 0:
        betas = data['betas']
        if betas.ndim > 1:
            betas = betas[0]  # Use first frame's betas
        betas = betas[:10]  # Use first 10 shape parameters
    else:
        betas = np.zeros(10, dtype=np.float64)
    
    print(f"[convert] Converting rotation matrices to Rodrigues vectors...")
    print(f"[convert] NOTE: Input data is in Y-down coordinate system (PHALP/OpenCV)")
    print(f"[convert] Addon will apply coordinate system correction for AMASS format")
    
    # IMPORTANT: Our NPZ data is in Y-down coordinate system (PHALP output)
    # AMASS format expects Y-up coordinate system
    # We need to apply 180° X-axis rotation to flip Y-down → Y-up
    R_FLIP_Y = np.array([
        [1.0,  0.0,  0.0],
        [0.0, -1.0,  0.0],
        [0.0,  0.0, -1.0]
    ], dtype=np.float64)
    
    # Convert rotation matrices to Rodrigues vectors
    poses = np.zeros((T, 55, 3), dtype=np.float64)
    
    for t in range(T):
        # Root (pelvis) - apply Y-down to Y-up conversion
        R_root_corrected = R_FLIP_Y @ R_root[t] @ R_FLIP_Y.T
        poses[t, 0] = rotmat_to_rodrigues(R_root_corrected)
        
        # Body joints (23 joints: left_hip to right_thumb3)
        for j in range(23):
            R_body_corrected = R_FLIP_Y @ R_body[t, j] @ R_FLIP_Y.T
            poses[t, j + 1] = rotmat_to_rodrigues(R_body_corrected)
        
        # Remaining joints (jaw, eyes, hands) - set to zero
        # joints 24-54 (jaw=24, eyes=25-26, hands=27-54)
        poses[t, 24:] = 0.0
    
    # Flatten poses to (T, 165)
    poses_flat = poses.reshape(T, -1)
    
    # Also flip translation Y and Z to match coordinate system
    trans_corrected = trans.copy()
    trans_corrected[:, 1] = -trans[:, 1]  # Flip Y
    trans_corrected[:, 2] = -trans[:, 2]  # Flip Z
    
    # Create AMASS format NPZ
    amass_data = {
        'trans': trans_corrected.astype(np.float32),
        'gender': np.array(gender),  # Can be string or bytes
        'mocap_framerate': fps,
        'betas': betas.astype(np.float32),
        'poses': poses_flat.astype(np.float32)
    }
    
    print(f"[convert] Saving AMASS format NPZ: {output_path}")
    np.savez(output_path, **amass_data)
    print(f"[convert] Conversion complete")
    
    return output_path


def main_blender(args):
    """Main function running inside Blender."""
    ensure_blender()
    import bpy
    import addon_utils
    
    print("\n" + "="*70)
    print("SMPL-X NPZ to FBX Converter")
    print("="*70)
    
    # Check if SMPL-X addon is installed and enabled
    addon_name = "smplx_blender_addon"
    addon_enabled = False
    
    for mod in addon_utils.modules():
        if mod.__name__ == addon_name:
            loaded_default, loaded_state = addon_utils.check(addon_name)
            if not loaded_state:
                addon_utils.enable(addon_name, default_set=True)
                print(f"[addon] Enabled {addon_name}")
            else:
                print(f"[addon] {addon_name} already enabled")
            addon_enabled = True
            break
    
    if not addon_enabled:
        raise RuntimeError(
            f"SMPL-X addon not found! Please install from https://smpl-x.is.tue.mpg.de/"
        )
    
    # Verify addon has required operators
    if not hasattr(bpy.ops.object, 'smplx_add_animation'):
        raise RuntimeError(
            "SMPL-X addon missing smplx_add_animation operator. "
            "Please install the official addon from https://smpl-x.is.tue.mpg.de/"
        )
    
    # Convert our NPZ format to AMASS format
    temp_dir = Path(args.npz).parent / "tmp_amass"
    temp_dir.mkdir(exist_ok=True)
    
    amass_npz = temp_dir / f"{Path(args.npz).stem}_amass.npz"
    convert_to_amass_format(args.npz, str(amass_npz), args.gender, args.fps)
    
    # Clean scene
    print("\n[blender] Cleaning scene...")
    bpy.ops.object.select_all(action='SELECT')
    if bpy.context.selected_objects:
        bpy.ops.object.delete()
    
    # Use addon's animation import
    print(f"\n[blender] Importing animation using SMPL-X addon...")
    print(f"[blender] Gender: {args.gender}")
    print(f"[blender] FPS: {args.fps}")
    print(f"[blender] Format: AMASS (Y-up)")
    
    # Set addon properties
    bpy.context.window_manager.smplx_tool.smplx_version = "locked_head"
    bpy.context.window_manager.smplx_tool.smplx_gender = args.gender
    
    # Import animation
    # Note: We need to use the operator with file selection
    # Since we can't use the file browser in background mode, we'll call it directly
    try:
        bpy.ops.object.smplx_add_animation(
            filepath=str(amass_npz),
            anim_format="AMASS",
            rest_position="SMPL-X",  # Use default rest position
            hand_reference="FLAT",
            keyframe_corrective_pose_weights=False,
            target_framerate=args.fps
        )
        print("[blender] Animation imported successfully")
    except Exception as e:
        print(f"[blender] Error importing animation: {e}")
        raise
    
    # Find the created mesh
    mesh_obj = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and 'SMPLX' in obj.name:
            mesh_obj = obj
            break
    
    if mesh_obj is None:
        raise RuntimeError("Failed to find SMPL-X mesh after animation import")
    
    bpy.context.view_layer.objects.active = mesh_obj
    print(f"[blender] Active mesh: {mesh_obj.name}")
    
    # Export FBX using addon's export
    print(f"\n[blender] Exporting FBX to: {args.out}")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    
    try:
        bpy.ops.object.smplx_export_fbx(
            filepath=args.out,
            export_shape_keys="SHAPE_POSECORRECTIVES",  # Export all blend shapes
            target_format=args.target_format
        )
        print("[blender] FBX exported successfully")
    except Exception as e:
        print(f"[blender] Error exporting FBX: {e}")
        raise
    
    # Clean up temporary AMASS NPZ
    if amass_npz.exists():
        amass_npz.unlink()
        print(f"[cleanup] Removed temporary file: {amass_npz}")
    
    print("\n" + "="*70)
    print("CONVERSION COMPLETE")
    print("="*70)
    print(f"Output: {args.out}")
    print(f"Format: {args.target_format}")
    print(f"Gender: {args.gender}")
    print(f"FPS: {args.fps}")
    print("="*70 + "\n")


if __name__ == '__main__':
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    args = parse_args(argv)
    main_blender(args)
