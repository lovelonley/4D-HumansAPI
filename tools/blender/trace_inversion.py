#!/usr/bin/env python3
"""
Trace the entire workflow to find where the inversion happens.

Workflow:
1. PHALP tracking -> PKL (R_root, R_body in SMPL format)
2. extract_track_for_tid.py -> NPZ (extracted single track)
3. adapt_smoothnet.py -> NPZ (smoothed)
4. Blender script -> FBX

This script checks each stage.
"""

import argparse
import sys
import numpy as np
from pathlib import Path

def check_rotation_orientation(R, name="Rotation"):
    """
    Check if a rotation matrix causes inversion by applying it to a standard up vector.
    SMPL standard: Y-up (0, 1, 0)
    """
    up_vector = np.array([0, 1, 0])
    rotated = R @ up_vector
    
    print(f"\n{name}:")
    print(f"  Matrix:")
    for row in R:
        print(f"    [{', '.join(f'{x:7.4f}' for x in row)}]")
    print(f"  Standard up (0,1,0) -> {rotated}")
    print(f"  Y component: {rotated[1]:.4f}")
    
    if rotated[1] > 0:
        print(f"  ✓ CORRECT orientation (up is still up)")
        return True
    else:
        print(f"  ✗ INVERTED orientation (up is now down)")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True, help="Task ID to trace")
    parser.add_argument("--base-dir", default=".", help="Base directory")
    args = parser.parse_args()
    
    base = Path(args.base_dir)
    task_id = args.task_id
    
    print("="*70)
    print("TRACING WORKFLOW INVERSION")
    print("="*70)
    
    # Stage 1: Check PKL output
    print("\n" + "="*70)
    print("STAGE 1: PHALP Tracking Output (PKL)")
    print("="*70)
    
    pkl_files = list((base / "outputs" / "results").glob(f"demo_*{task_id}*.pkl"))
    if not pkl_files:
        pkl_files = list((base / "outputs" / "results").glob(f"demo_*.pkl"))
    
    if pkl_files:
        import joblib
        pkl_path = pkl_files[0]
        print(f"\nLoading: {pkl_path}")
        
        try:
            data = joblib.load(pkl_path)
            print(f"Type: {type(data)}")
            print(f"Keys: {len(data)} frames")
            
            # Get first frame with data
            first_key = list(data.keys())[0]
            frame_data = data[first_key]
            
            if isinstance(frame_data, dict):
                print(f"\nFirst frame keys: {list(frame_data.keys())[:10]}")
                
                # Check if SMPL data exists
                if 'smpl' in frame_data:
                    smpl_list = frame_data['smpl']
                    if len(smpl_list) > 0:
                        smpl = smpl_list[0]
                        if 'global_orient' in smpl:
                            global_orient = np.array(smpl['global_orient'])
                            print(f"\nSMPL global_orient shape: {global_orient.shape}")
                            print(f"SMPL global_orient (axis-angle): {global_orient}")
                            
                            # Convert axis-angle to rotation matrix
                            from scipy.spatial.transform import Rotation as R
                            if global_orient.size == 3:
                                rot = R.from_rotvec(global_orient.reshape(3))
                                R_root = rot.as_matrix()
                                check_rotation_orientation(R_root, "PKL R_root (from global_orient)")
        except Exception as e:
            print(f"Error loading PKL: {e}")
    else:
        print("No PKL file found")
    
    # Stage 2: Check extracted NPZ
    print("\n" + "="*70)
    print("STAGE 2: Extracted Track (NPZ)")
    print("="*70)
    
    extracted_npz = base / "tmp" / f"{task_id}_tid1.npz"
    if extracted_npz.exists():
        print(f"\nLoading: {extracted_npz}")
        data = np.load(extracted_npz)
        print(f"Keys: {list(data.keys())}")
        
        R_root = data['R_root']
        print(f"\nR_root shape: {R_root.shape}")
        check_rotation_orientation(R_root[0], "Extracted R_root[0]")
    else:
        print(f"Not found: {extracted_npz}")
    
    # Stage 3: Check smoothed NPZ
    print("\n" + "="*70)
    print("STAGE 3: Smoothed Track (NPZ)")
    print("="*70)
    
    smoothed_npz = base / "tmp" / f"{task_id}_smoothed.npz"
    if smoothed_npz.exists():
        print(f"\nLoading: {smoothed_npz}")
        data = np.load(smoothed_npz)
        print(f"Keys: {list(data.keys())}")
        
        R_root = data['R_root']
        print(f"\nR_root shape: {R_root.shape}")
        check_rotation_orientation(R_root[0], "Smoothed R_root[0]")
    else:
        print(f"Not found: {smoothed_npz}")
    
    print("\n" + "="*70)
    print("TRACE COMPLETE")
    print("="*70)


if __name__ == '__main__':
    main()

