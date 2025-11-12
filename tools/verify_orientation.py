#!/usr/bin/env python3
"""
验证 PKL 和 NPZ 中人物方向是否一致
比较第一帧的：头、左手、右手、脚的位置
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
            'global_orient': np.array(smpl['global_orient']).reshape(1, 3, 3),
            'body_pose': np.array(smpl['body_pose']).reshape(1, 23, 3, 3),
            'betas': np.array(smpl.get('betas', np.zeros(10))).reshape(1, 10)
        }
    
    return None


def get_smpl_model_path():
    """查找 SMPL 模型路径"""
    import os
    candidates = [
        os.path.expanduser('~/.cache/4DHumans/data/smpl'),
        os.path.expanduser('~/.cache/phalp/3D/models/smpl'),
        'data/smpl'
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"SMPL 模型未找到，检查过的路径: {candidates}")


def get_key_joints(smpl_params):
    """
    用 SMPL 计算关键点：头(15)、左手(20)、右手(21)、左脚(10)、右脚(11)
    """
    try:
        import torch
        from smplx import SMPL
        
        model_path = get_smpl_model_path()
        smpl = SMPL(model_path=model_path, gender='neutral', batch_size=1)
        
        output = smpl(
            global_orient=torch.tensor(smpl_params['global_orient'], dtype=torch.float32),
            body_pose=torch.tensor(smpl_params['body_pose'], dtype=torch.float32),
            betas=torch.tensor(smpl_params['betas'], dtype=torch.float32)
        )
        
        joints = output.joints[0].detach().numpy()  # (45, 3)
        
        # SMPL 关节索引
        HEAD = 15
        LEFT_WRIST = 20
        RIGHT_WRIST = 21
        LEFT_FOOT = 10
        RIGHT_FOOT = 11
        
        return {
            'head': joints[HEAD],
            'left_hand': joints[LEFT_WRIST],
            'right_hand': joints[RIGHT_WRIST],
            'left_foot': joints[LEFT_FOOT],
            'right_foot': joints[RIGHT_FOOT]
        }
    except Exception as e:
        print(f"Error: {e}")
        print("需要安装: pip install smplx torch")
        sys.exit(1)


def print_joints(joints, name):
    print(f"\n=== {name} ===")
    for key, pos in joints.items():
        print(f"{key:12s}: [{pos[0]:8.4f}, {pos[1]:8.4f}, {pos[2]:8.4f}]")


def analyze_orientation(joints):
    """分析方向"""
    head = joints['head']
    left_foot = joints['left_foot']
    right_foot = joints['right_foot']
    
    avg_foot_y = (left_foot[1] + right_foot[1]) / 2
    head_foot_diff = head[1] - avg_foot_y
    
    print(f"\nHead Y: {head[1]:.4f}, Feet Y: {avg_foot_y:.4f}, Diff: {head_foot_diff:.4f}")
    
    if head_foot_diff > 0.3:
        print("→ 正立 (头在上)")
    elif head_foot_diff < -0.3:
        print("→ 倒立 (头在下)")
    else:
        print("→ 方向不明")
    
    # 左右手朝向（判断是否镜像）
    left_right_x = joints['left_hand'][0] - joints['right_hand'][0]
    print(f"\nLeft-Right X: {left_right_x:.4f}")
    if left_right_x < 0:
        print("→ 可能镜像了（左手在右边）")


def compare_joints(joints1, joints2):
    print("\n" + "=" * 60)
    print("差异对比")
    print("=" * 60)
    
    all_close = True
    for key in joints1.keys():
        diff = np.abs(joints1[key] - joints2[key])
        max_diff = np.max(diff)
        print(f"{key:12s}: max_diff = {max_diff:.6f}", end="")
        if max_diff < 1e-4:
            print(" ✓")
        else:
            print(" ✗ 不一致！")
            all_close = False
    
    return all_close


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkl', required=True)
    ap.add_argument('--npz', required=True)
    ap.add_argument('--tid', type=int, default=1)
    args = ap.parse_args()
    
    print("=" * 60)
    print("验证 PKL → NPZ 方向一致性")
    print("=" * 60)
    
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
        'global_orient': npz_data['R_root'][0:1],
        'body_pose': npz_data['R_body'][0:1],
        'betas': npz_data['betas'][0:1] if 'betas' in npz_data else np.zeros((1, 10))
    }
    
    # 3. 计算关键点
    print("\n[3] 计算关键点（需要 SMPL 模型）...")
    pkl_joints = get_key_joints(pkl_smpl)
    npz_joints = get_key_joints(npz_smpl)
    
    # 4. 显示位置
    print_joints(pkl_joints, "PKL 关键点")
    analyze_orientation(pkl_joints)
    
    print_joints(npz_joints, "NPZ 关键点")
    analyze_orientation(npz_joints)
    
    # 5. 对比
    all_match = compare_joints(pkl_joints, npz_joints)
    
    print("\n" + "=" * 60)
    print("结论")
    print("=" * 60)
    if all_match:
        print("✓ PKL 和 NPZ 完全一致")
    else:
        print("✗ PKL 和 NPZ 不一致")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
