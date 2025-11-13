#!/usr/bin/env python3
"""
Motion Analyzer: Three-way verification system for separating camera and person motion.

Implements three independent analyzers:
1. Heuristic Filter: Threshold-based analysis
2. Pelvis Tracking: 3D joint-based analysis
3. Perspective Analysis: 2D bbox-based analysis

Combines results using weighted voting for final decision.
"""

from typing import Dict, Any, Optional
import numpy as np


class MotionAnalyzer:
    """
    Analyzes camera and person motion from PHALP tracking data.
    
    Uses three independent methods to separate camera motion from person motion:
    - Heuristic: Simple threshold-based filtering
    - Pelvis: 3D pelvis position tracking
    - Perspective: 2D bbox size and position analysis
    """
    
    def __init__(self, npz_data: Dict[str, np.ndarray]):
        """
        Initialize analyzer with NPZ data.
        
        Args:
            npz_data: Dictionary containing:
                - camera: (T, 3) camera translation
                - 3d_joints: (T, 45, 3) 3D joint positions (optional)
                - bbox: (T, 4) 2D bounding boxes (optional)
                - center: (T, 2) bbox centers (optional)
                - scale: (T,) bbox scales (optional)
                - img_size: (T, 2) image dimensions (optional)
        """
        self.camera = npz_data['camera']
        self.T = self.camera.shape[0]
        
        # Normalize camera (relative to first frame)
        self.camera_norm = self.camera - self.camera[0]
        
        # Optional data for advanced analysis
        self.joints_3d = npz_data.get('3d_joints')
        self.bbox = npz_data.get('bbox')
        self.center = npz_data.get('center')
        self.scale = npz_data.get('scale')
        self.img_size = npz_data.get('img_size')
        
        # Pelvis tracking (if joints available)
        if self.joints_3d is not None and self.joints_3d.size > 0:
            self.pelvis_pos = self.joints_3d[:, 0, :]  # Joint 0 = pelvis
            self.pelvis_norm = self.pelvis_pos - self.pelvis_pos[0]
        else:
            self.pelvis_pos = None
            self.pelvis_norm = None
    
    def analyze(self) -> Dict[str, Any]:
        """
        Run all three analyzers and combine results.
        
        Returns:
            Dictionary containing:
                - trans_corrected: (T, 3) corrected translation
                - method: Primary method used
                - confidence: Overall confidence score
                - details: Detailed results from each analyzer
        """
        print("[motion] Running motion analysis...")
        
        # Run three analyzers
        result_1 = self.analyzer_1_heuristic()
        result_2 = self.analyzer_2_pelvis()
        result_3 = self.analyzer_3_perspective()
        
        # Integrate results
        final = self.integrate_results(result_1, result_2, result_3)
        
        return final
    
    def analyzer_1_heuristic(self) -> Dict[str, Any]:
        """
        Heuristic analyzer: Simple threshold-based filtering.
        
        Assumptions:
        - Large Z changes (>5m) → camera forward/backward motion
        - Large XY changes (>0.5m) → possible camera pan
        
        Returns:
            Analysis result with proposed translation and confidence
        """
        z_range = self.camera_norm[:, 2].ptp()  # peak-to-peak
        xy_max = np.linalg.norm(self.camera_norm[:, :2], axis=1).max()
        
        # Decisions
        z_is_camera = z_range > 5.0
        xy_is_large = xy_max > 0.5
        
        # Proposed translation
        trans_proposed = self.camera_norm.copy()
        
        if z_is_camera:
            trans_proposed[:, 2] = 0  # Ignore Z
        
        if xy_is_large:
            # Scale XY to reasonable range
            scale = 0.5 / xy_max
            trans_proposed[:, :2] *= scale
        
        # Confidence: higher if clear camera motion detected
        confidence = 0.5
        if z_is_camera:
            confidence += 0.2
        if xy_is_large:
            confidence += 0.1
        
        return {
            'name': 'Heuristic',
            'trans': trans_proposed,
            'confidence': min(confidence, 1.0),
            'reasoning': {
                'z_is_camera': z_is_camera,
                'xy_is_large': xy_is_large,
                'z_range': z_range,
                'xy_max': xy_max
            }
        }
    
    def analyzer_2_pelvis(self) -> Dict[str, Any]:
        """
        Pelvis tracking analyzer: Uses 3D pelvis position.
        
        Key insights:
        - Pelvis is body center, represents overall person position
        - Pelvis motion is usually smoother than camera shake
        - Pelvis XY is more reliable than Z (depth ambiguity)
        
        Returns:
            Analysis result with proposed translation and confidence
        """
        if self.pelvis_norm is None:
            # No pelvis data, return low-confidence neutral result
            return {
                'name': 'Pelvis',
                'trans': self.camera_norm.copy(),
                'confidence': 0.3,
                'reasoning': {
                    'available': False,
                    'message': 'No 3d_joints data available'
                }
            }
        
        # Compare pelvis vs camera
        pelvis_xy = self.pelvis_norm[:, :2]
        camera_xy = self.camera_norm[:, :2]
        
        # XY difference
        xy_diff = np.linalg.norm(pelvis_xy - camera_xy, axis=1).mean()
        
        # Smoothness analysis (jerk = 3rd derivative)
        pelvis_vel = np.diff(self.pelvis_pos, axis=0)
        camera_vel = np.diff(self.camera, axis=0)
        
        pelvis_acc = np.diff(pelvis_vel, axis=0)
        camera_acc = np.diff(camera_vel, axis=0)
        
        pelvis_jerk = np.linalg.norm(pelvis_acc, axis=1).std()
        camera_jerk = np.linalg.norm(camera_acc, axis=1).std()
        
        pelvis_smoother = pelvis_jerk < camera_jerk
        
        # Pelvis Z range
        pelvis_z_range = self.pelvis_norm[:, 2].ptp()
        
        # Proposed translation
        trans_proposed = self.camera_norm.copy()
        
        if pelvis_smoother and xy_diff < 0.2:
            # Pelvis is smoother and consistent → use pelvis XY
            trans_proposed[:, :2] = pelvis_xy
        
        if pelvis_z_range < 1.0:
            # Pelvis Z stable → person not moving forward/backward
            trans_proposed[:, 2] = 0
        else:
            # Pelvis Z changing → might be real movement, but scale down
            trans_proposed[:, 2] *= 0.3
        
        # Confidence based on smoothness and consistency
        confidence = 0.5
        if pelvis_smoother:
            confidence += 0.3
        if pelvis_z_range < 1.0:
            confidence += 0.2
        
        return {
            'name': 'Pelvis',
            'trans': trans_proposed,
            'confidence': min(confidence, 1.0),
            'reasoning': {
                'available': True,
                'pelvis_smoother': pelvis_smoother,
                'xy_diff': xy_diff,
                'pelvis_z_range': pelvis_z_range,
                'pelvis_jerk': pelvis_jerk,
                'camera_jerk': camera_jerk
            }
        }
    
    def analyzer_3_perspective(self) -> Dict[str, Any]:
        """
        Perspective analyzer: Uses 2D bbox size and position.
        
        Key insights:
        - Camera zoom: bbox size ∝ 1/depth
        - Camera pan: bbox center moves away from image center
        - Person move: bbox changes but perspective relationship holds
        
        Returns:
            Analysis result with proposed translation and confidence
        """
        if self.bbox is None or self.center is None or self.img_size is None:
            # No bbox data, return low-confidence neutral result
            return {
                'name': 'Perspective',
                'trans': self.camera_norm.copy(),
                'confidence': 0.3,
                'reasoning': {
                    'available': False,
                    'message': 'No bbox/center/img_size data available'
                }
            }
        
        # Bbox area
        bbox_area = self.bbox[:, 2] * self.bbox[:, 3]
        area_ratio = bbox_area / (bbox_area[0] + 1e-9)
        
        # Expected scale from depth change (perspective projection)
        z0 = self.camera[0, 2]
        z_change = self.camera_norm[:, 2]
        expected_scale = 1.0 / (1.0 + z_change / (z0 + 1e-9))
        
        # Compare actual vs expected
        scale_error = np.abs(area_ratio - expected_scale).mean()
        scale_matches = scale_error < 0.15
        
        # Bbox center offset from image center
        img_center = self.img_size[0] / 2.0
        center_offset = np.linalg.norm(self.center - img_center, axis=1)
        center_offset_norm = center_offset / (self.img_size[0, 0] + 1e-9)
        
        bbox_centered = center_offset_norm.mean() < 0.15
        
        # Proposed translation
        trans_proposed = self.camera_norm.copy()
        
        # Decision logic
        if scale_matches and bbox_centered:
            # Bbox size matches perspective + centered → camera zoom
            trans_proposed[:, 2] = 0
            confidence = 0.9
            motion_type = 'camera_zoom'
        elif not bbox_centered:
            # Bbox off-center → camera pan or person move
            # Conservative: scale XY and ignore Z
            xy_max = np.linalg.norm(trans_proposed[:, :2], axis=1).max()
            if xy_max > 0.5:
                trans_proposed[:, :2] *= 0.5 / xy_max
            trans_proposed[:, 2] = 0
            confidence = 0.6
            motion_type = 'camera_pan_or_person'
        else:
            # Uncertain
            trans_proposed[:, 2] = 0
            confidence = 0.5
            motion_type = 'uncertain'
        
        return {
            'name': 'Perspective',
            'trans': trans_proposed,
            'confidence': confidence,
            'reasoning': {
                'available': True,
                'scale_matches': scale_matches,
                'bbox_centered': bbox_centered,
                'scale_error': scale_error,
                'center_offset_mean': center_offset_norm.mean(),
                'motion_type': motion_type
            }
        }
    
    def integrate_results(self, r1: Dict, r2: Dict, r3: Dict) -> Dict[str, Any]:
        """
        Integrate results from three analyzers.
        
        Strategy:
        1. Weighted average based on confidence
        2. Majority voting for Z-axis decision
        3. High-confidence override (>0.85)
        
        Args:
            r1, r2, r3: Results from three analyzers
        
        Returns:
            Final integrated result
        """
        # Weighted average
        total_confidence = r1['confidence'] + r2['confidence'] + r3['confidence']
        
        w1 = r1['confidence'] / total_confidence
        w2 = r2['confidence'] / total_confidence
        w3 = r3['confidence'] / total_confidence
        
        trans_weighted = (
            w1 * r1['trans'] +
            w2 * r2['trans'] +
            w3 * r3['trans']
        )
        
        # Majority voting for Z-axis
        z_votes = [
            np.allclose(r1['trans'][:, 2], 0, atol=0.01),
            np.allclose(r2['trans'][:, 2], 0, atol=0.01),
            np.allclose(r3['trans'][:, 2], 0, atol=0.01)
        ]
        z_should_zero = sum(z_votes) >= 2
        
        if z_should_zero:
            trans_weighted[:, 2] = 0
        
        # High-confidence override
        max_conf = max(r1['confidence'], r2['confidence'], r3['confidence'])
        
        if max_conf > 0.85:
            if r1['confidence'] == max_conf:
                trans_final = r1['trans']
                primary_method = 'Heuristic'
            elif r2['confidence'] == max_conf:
                trans_final = r2['trans']
                primary_method = 'Pelvis'
            else:
                trans_final = r3['trans']
                primary_method = 'Perspective'
        else:
            trans_final = trans_weighted
            primary_method = 'Weighted Average'
        
        # Final safety check: absolute limit
        xy_max = np.linalg.norm(trans_final[:, :2], axis=1).max()
        if xy_max > 1.0:
            trans_final[:, :2] *= 1.0 / xy_max
        
        return {
            'trans_corrected': trans_final,
            'method': primary_method,
            'confidence': max_conf if max_conf > 0.85 else (total_confidence / 3),
            'z_votes': z_votes,
            'z_decision': 'zero' if z_should_zero else 'keep',
            'weights': {
                'heuristic': w1,
                'pelvis': w2,
                'perspective': w3
            },
            'details': {
                'heuristic': r1,
                'pelvis': r2,
                'perspective': r3
            }
        }


def analyze_motion(npz_path: str) -> Dict[str, Any]:
    """
    Convenience function to analyze motion from NPZ file.
    
    Args:
        npz_path: Path to NPZ file
    
    Returns:
        Motion analysis result
    """
    data = np.load(npz_path)
    analyzer = MotionAnalyzer(dict(data))
    return analyzer.analyze()


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python motion_analyzer.py <npz_file>")
        sys.exit(1)
    
    result = analyze_motion(sys.argv[1])
    
    print("\n" + "=" * 70)
    print("MOTION ANALYSIS RESULT")
    print("=" * 70)
    print(f"Primary method: {result['method']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Z decision: {result['z_decision']}")
    print(f"\nTranslation range:")
    trans = result['trans_corrected']
    print(f"  X: [{trans[:, 0].min():.3f}, {trans[:, 0].max():.3f}]")
    print(f"  Y: [{trans[:, 1].min():.3f}, {trans[:, 1].max():.3f}]")
    print(f"  Z: [{trans[:, 2].min():.3f}, {trans[:, 2].max():.3f}]")
    print("=" * 70)

