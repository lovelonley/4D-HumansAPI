# Git Submodules 使用说明

## 当前 Submodules

- **phalp**: PHALP 追踪库
  - Path: `phalp/`
  - Commit: 677074a9bd7acac58c0b98a31b04ae54b93dcd2f
  - Branch: master
  - URL: https://github.com/brjathu/PHALP.git

- **smoothnet**: SmoothNet 平滑库
  - Path: `smoothnet/`
  - Commit: c03e93e8a14f55b9aa087dced2751a7a5e2d50b0
  - Branch: main
  - URL: https://github.com/cure-lab/SmoothNet.git

**注意**：目录名使用小写（`phalp/`、`smoothnet/`），与代码中的导入路径一致。

## 克隆项目（包含 submodules）

```bash
git clone --recursive https://github.com/lovelonley/4D-HumansAPI.git
```

或者如果使用原始仓库：

```bash
git clone --recursive https://github.com/shubham-goel/4D-Humans.git
```

或者分步：

```bash
git clone https://github.com/lovelonley/4D-HumansAPI.git
cd 4D-Humans
git submodule update --init --recursive
```

## 更新 Submodules

```bash
# 更新到最新版本
git submodule update --remote

# 更新到特定 commit
cd phalp
git checkout <commit-hash>
cd ../smoothnet
git checkout <commit-hash>
cd ..
git add phalp smoothnet
git commit -m "Update submodules"
```

## 检查 Submodules 状态

```bash
git submodule status
```

## 恢复备份

如果出现问题，可以恢复：

```bash
git checkout backup-before-git-optimization-20251113-154106
```
