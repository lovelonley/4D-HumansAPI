#!/usr/bin/env python3
"""
验证 PKL 和 NPZ 中人物方向是否一致
直接比较 SMPL 旋转矩阵，不需要 SMPL 模型
"""

import argparse
import sys
import numpy as np


def load_pkl(pkl_path):
    try:
        import joblib
        return joblib.load(pkl_path)
    except:
        import pickle
        with open(pkl_path, 'rb') as f:
            return pickle.load(f)


def get_pkl_first_frame(pkl_data, tid):
    """从 PKL 获取指定 tid 的第一帧 SMPL 参数"""
    for frame_key in sorted(pkl_data.keys()):
        frame = pkl_data[frame_key]
        if not isinstance(frame, dict):
            continue
        
        tids = frame.get('tracked_ids', [])
        if tid not in tids:
            continue
        
        idx = tids.index(tid)
        smpl_list = frame.get('smpl', [])
        if idx >= len(smpl_list) or smpl_list[idx] in [None, -1]:
            continue
        
        smpl = smpl_list[idx]
        return {
            'R_root': np.array(smpl['global_orient']).reshape(3, 3),
            'R_body': np.array(smpl['body_pose']).reshape(23, 3, 3)
        }
    
    return None


def analyze_rotation_matrix(R, name):
    """
    分析旋转矩阵的方向
    旋转矩阵的列向量 = 局部坐标轴在全局坐标系中的方向
    """
    print(f"\n=== {name} ===")
    print("R_root (pelvis 全局旋转):")
    print(R)
    
    # 列向量 = 局部轴在全局中的方向
    local_x = R[:, 0]  # 局部 X 轴（右）
    local_y = R[:, 1]  # 局部 Y 轴（上）
    local_z = R[:, 2]  # 局部 Z 轴（前）
    
    print(f"\n局部坐标轴在全局坐标系中的方向:")
    print(f"  X (右): [{local_x[0]:7.4f}, {local_x[1]:7.4f}, {local_x[2]:7.4f}]")
    print(f"  Y (上): [{local_y[0]:7.4f}, {local_y[1]:7.4f}, {local_y[2]:7.4f}]")
    print(f"  Z (前): [{local_z[0]:7.4f}, {local_z[1]:7.4f}, {local_z[2]:7.4f}]")
    
    # 判断上下方向
    print(f"\n上下方向判断 (Y轴):")
    if local_y[1] > 0.7:
        print(f"  ✓ 正立 (局部Y指向全局+Y, 分量={local_y[1]:.4f})")
    elif local_y[1] < -0.7:
        print(f"  ✗ 倒立 (局部Y指向全局-Y, 分量={local_y[1]:.4f})")
    else:
        print(f"  ? 倾斜 (Y分量={local_y[1]:.4f})")
    
    # 判断前后方向
    print(f"\n前后方向判断 (Z轴):")
    if local_z[2] > 0.7:
        print(f"  → 面向前方 (局部Z指向全局+Z, 分量={local_z[2]:.4f})")
    elif local_z[2] < -0.7:
        print(f"  → 面向后方 (局部Z指向全局-Z, 分量={local_z[2]:.4f})")
    else:
        print(f"  → 侧向 (Z分量={local_z[2]:.4f})")
    
    return {
        'local_y': local_y,
        'local_z': local_z,
        'upright': local_y[1] > 0.7,
        'inverted': local_y[1] < -0.7
    }


def compare_matrices(R1, R2):
    """比较两个旋转矩阵是否一致"""
    diff = np.abs(R1 - R2)
    max_diff = np.max(diff)
    mean_diff = np.mean(diff)
    
    print(f"\n旋转矩阵差异:")
    print(f"  最大差异: {max_diff:.6f}")
    print(f"  平均差异: {mean_diff:.6f}")
    
    if max_diff < 1e-5:
        print(f"  ✓ 完全一致")
        return True
    elif max_diff < 1e-3:
        print(f"  ≈ 基本一致 (可能是浮点精度)")
        return True
    else:
        print(f"  ✗ 不一致！")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkl', required=True)
    ap.add_argument('--npz', required=True)
    ap.add_argument('--tid', type=int, default=1)
    args = ap.parse_args()
    
    print("=" * 70)
    print("验证 PKL → NPZ 数据一致性和方向")
    print("=" * 70)
    
    # 1. 加载 PKL 第一帧
    print(f"\n[1] 加载 PKL: {args.pkl}")
    pkl_data = load_pkl(args.pkl)
    pkl_smpl = get_pkl_first_frame(pkl_data, args.tid)
    
    if pkl_smpl is None:
        print(f"错误: 找不到 tid={args.tid}")
        sys.exit(1)
    
    # 2. 加载 NPZ 第一帧
    print(f"[2] 加载 NPZ: {args.npz}")
    npz_data = np.load(args.npz)
    npz_smpl = {
        'R_root': npz_data['R_root'][0],
        'R_body': npz_data['R_body'][0]
    }
    
    # 3. 比较 R_root
    print("\n" + "=" * 70)
    print("对比 R_root (pelvis 全局旋转)")
    print("=" * 70)
    
    pkl_match = compare_matrices(pkl_smpl['R_root'], npz_smpl['R_root'])
    
    # 4. 分析方向
    print("\n" + "=" * 70)
    print("方向分析")
    print("=" * 70)
    
    pkl_orient = analyze_rotation_matrix(pkl_smpl['R_root'], "PKL")
    npz_orient = analyze_rotation_matrix(npz_smpl['R_root'], "NPZ")
    
    # 5. 结论
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)
    
    if pkl_match:
        print("✓ PKL 和 NPZ 的 R_root 完全一致")
    else:
        print("✗ PKL 和 NPZ 的 R_root 不一致")
    
    if pkl_orient['upright'] == npz_orient['upright']:
        print("✓ 方向一致")
    else:
        print("✗ 方向不一致")
    
    # 说明当前状态
    if pkl_orient['inverted']:
        print("\n⚠  数据显示角色是倒立的 (Y-down 坐标系)")
        print("   这是 PHALP 相机坐标系的预期行为")
        print("   导出 FBX 时需要处理这个翻转")
    elif pkl_orient['upright']:
        print("\n✓ 数据显示角色是正立的")
    
    sys.exit(0 if pkl_match else 1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
