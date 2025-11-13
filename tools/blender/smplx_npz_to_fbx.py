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

# Add tools directory to path for motion_analyzer
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from motion_analyzer import MotionAnalyzer
except ImportError:
    MotionAnalyzer = None
    print("[warning] motion_analyzer not found, motion analysis disabled")


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
        trans_raw = data['camera'].copy()  # (T, 3)
    else:
        trans_raw = np.zeros((T, 3), dtype=np.float64)
    
    # === MOTION ANALYSIS ===
    if MotionAnalyzer is not None and trans_raw.size > 0:
        print("\n" + "=" * 70)
        print("MOTION ANALYSIS")
        print("=" * 70)
        
        analyzer = MotionAnalyzer(dict(data))
        result = analyzer.analyze()
        
        # Print detailed analysis
        print(f"\n[Analysis 1] Heuristic:")
        h = result['details']['heuristic']
        print(f"  Z range: {h['reasoning']['z_range']:.2f}m")
        print(f"  XY max: {h['reasoning']['xy_max']:.2f}m")
        print(f"  Z is camera: {h['reasoning']['z_is_camera']}")
        print(f"  Confidence: {h['confidence']:.2f}")
        
        print(f"\n[Analysis 2] Pelvis:")
        p = result['details']['pelvis']
        if p['reasoning'].get('available'):
            print(f"  Pelvis smoother: {p['reasoning']['pelvis_smoother']}")
            print(f"  Pelvis Z range: {p['reasoning']['pelvis_z_range']:.2f}m")
            print(f"  XY diff: {p['reasoning']['xy_diff']:.3f}m")
            print(f"  Confidence: {p['confidence']:.2f}")
        else:
            print(f"  {p['reasoning']['message']}")
            print(f"  Confidence: {p['confidence']:.2f}")
        
        print(f"\n[Analysis 3] Perspective:")
        t = result['details']['perspective']
        if t['reasoning'].get('available'):
            print(f"  Scale matches: {t['reasoning']['scale_matches']}")
            print(f"  Bbox centered: {t['reasoning']['bbox_centered']}")
            print(f"  Motion type: {t['reasoning']['motion_type']}")
            print(f"  Confidence: {t['confidence']:.2f}")
        else:
            print(f"  {t['reasoning']['message']}")
            print(f"  Confidence: {t['confidence']:.2f}")
        
        print(f"\n[Decision]")
        print(f"  Primary method: {result['method']}")
        print(f"  Final confidence: {result['confidence']:.2f}")
        print(f"  Z decision: {result['z_decision']} (votes: {sum(result['z_votes'])}/3)")
        print(f"  Weights: H={result['weights']['heuristic']:.2f}, "
              f"P={result['weights']['pelvis']:.2f}, "
              f"T={result['weights']['perspective']:.2f}")
        
        # Use corrected translation
        trans = result['trans_corrected']
        
        print(f"\n[Final Translation]")
        print(f"  X: [{trans[:, 0].min():.3f}, {trans[:, 0].max():.3f}]")
        print(f"  Y: [{trans[:, 1].min():.3f}, {trans[:, 1].max():.3f}]")
        print(f"  Z: [{trans[:, 2].min():.3f}, {trans[:, 2].max():.3f}]")
        print("=" * 70 + "\n")
    else:
        # No motion analysis, use raw translation
        trans = trans_raw
        print("[convert] Motion analysis skipped (no analyzer or no camera data)")
    
    # Get betas (default to zeros if not available)
    if 'betas' in data and data['betas'].size > 0:
        betas = data['betas']
        if betas.ndim > 1:
            betas = betas[0]  # Use first frame's betas
        betas = betas[:10]  # Use first 10 shape parameters
    else:
        betas = np.zeros(10, dtype=np.float64)
    
    print(f"\n[convert] Converting rotation matrices to Rodrigues vectors...")
    print(f"[convert] NOTE: Applying 180° X-rotation to root for correct orientation")
    
    # IMPORTANT INSIGHT:
    # - Body joint rotations are in correct SMPL model space (local rotations)
    # - But the global orientation (root) needs 180° X-flip to match PHALP rendering
    # - PHALP applies this flip to vertices; we apply it to root rotation instead
    
    # 180° rotation around X-axis for flipping upside-down to upright
    R_FLIP_X_180 = np.array([
        [1.0,  0.0,  0.0],
        [0.0, -1.0,  0.0],
        [0.0,  0.0, -1.0]
    ], dtype=np.float64)
    
    # Convert rotation matrices to Rodrigues vectors
    poses = np.zeros((T, 55, 3), dtype=np.float64)
    
    for t in range(T):
        # Root (pelvis) - apply 180° X-flip to match PHALP's vertex transformation
        R_root_flipped = R_FLIP_X_180 @ R_root[t]
        poses[t, 0] = rotmat_to_rodrigues(R_root_flipped)
        
        # Body joints (23 joints) - keep as-is (local rotations are correct)
        for j in range(23):
            poses[t, j + 1] = rotmat_to_rodrigues(R_body[t, j])
        
        # Remaining joints (jaw, eyes, hands) - set to zero
        # joints 24-54 (jaw=24, eyes=25-26, hands=27-54)
        poses[t, 24:] = 0.0
    
    # Flatten poses to (T, 165)
    poses_flat = poses.reshape(T, -1)
    
    # Translation: already corrected by motion analysis above
    trans_corrected = trans
    
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
    print(f"[blender] Format: SMPL-X (Y-up, no additional rotation)")
    
    # Set addon properties
    bpy.context.window_manager.smplx_tool.smplx_version = "locked_head"
    bpy.context.window_manager.smplx_tool.smplx_gender = args.gender
    
    # Import animation
    # Use SMPL-X format (not AMASS) to avoid additional -90° X-axis rotation
    # Our data is already Y-up after applying the 180° flip
    try:
        bpy.ops.object.smplx_add_animation(
            filepath=str(amass_npz),
            anim_format="SMPL-X",  # Changed from "AMASS" to avoid extra rotation
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
