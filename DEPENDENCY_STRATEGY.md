# 依赖检查策略 - 强制要求

## 核心原则

**所有依赖必须在服务启动时可用，否则服务无法启动。不提供降级策略。**

---

## 1. SmoothNet 检查点

### 要求
- ✅ **必须存在**: `SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar`
- ✅ **必须可加载**: PyTorch 能成功加载检查点
- ✅ **必须可导入**: SmoothNet 模块必须在 PYTHONPATH 中
- ❌ **不允许降级**: 不使用 Moving Average fallback
- ❌ **不允许跳过**: 平滑步骤是必需的

### 启动检查代码

```python
# api/services/pipeline.py

def _check_smoothnet_or_fail(self):
    """
    检查 SmoothNet 可用性，不可用则抛出异常
    
    Raises:
        RuntimeError: SmoothNet 不可用
    """
    checkpoint = Path(settings.SMOOTHNET_CHECKPOINT)
    
    # 1. 检查检查点文件
    if not checkpoint.exists():
        raise RuntimeError(
            f"❌ SmoothNet checkpoint not found: {checkpoint}\n"
            f"\n"
            f"Please download from:\n"
            f"  https://drive.google.com/drive/folders/19Cu-_gqylFZAOTmHXzK52C80DKb0Tfx_\n"
            f"\n"
            f"And place at:\n"
            f"  {checkpoint}\n"
            f"\n"
            f"Or run:\n"
            f"  mkdir -p {checkpoint.parent}\n"
            f"  # Download checkpoint_8.pth.tar to the above directory"
        )
    
    # 2. 检查 PyTorch
    try:
        import torch
        if not torch.cuda.is_available():
            logger.warning("⚠️  CUDA not available, SmoothNet will run on CPU (slower)")
    except ImportError:
        raise RuntimeError(
            "❌ PyTorch not installed\n"
            f"\n"
            f"Please install:\n"
            f"  pip install torch torchvision"
        )
    
    # 3. 检查 SmoothNet 模块
    try:
        import sys
        sys.path.insert(0, str(self.smoothnet_dir))
        sys.path.insert(0, str(self.smoothnet_dir / "lib"))
        from lib.models.smoothnet import SmoothNet
        logger.info(f"✓ SmoothNet module available")
    except ImportError as e:
        raise RuntimeError(
            f"❌ SmoothNet module not found: {e}\n"
            f"\n"
            f"Please ensure SmoothNet directory exists:\n"
            f"  {self.smoothnet_dir}\n"
            f"\n"
            f"And install dependencies:\n"
            f"  pip install -r SmoothNet/requirements.txt"
        )
    
    # 4. 验证检查点可加载
    try:
        import torch
        ckpt = torch.load(checkpoint, map_location='cpu')
        if 'state_dict' not in ckpt and not isinstance(ckpt, dict):
            raise ValueError("Invalid checkpoint format")
        logger.info(f"✓ SmoothNet checkpoint validated: {checkpoint.name}")
    except Exception as e:
        raise RuntimeError(
            f"❌ Failed to load checkpoint: {e}\n"
            f"\n"
            f"Checkpoint may be corrupted, please re-download from:\n"
            f"  https://drive.google.com/drive/folders/19Cu-_gqylFZAOTmHXzK52C80DKb0Tfx_"
        )
    
    logger.info(f"✓ SmoothNet ready: {checkpoint}")
```

### 用户安装文档

```markdown
## SmoothNet 检查点安装（必需）

### 下载

**Google Drive**: https://drive.google.com/drive/folders/19Cu-_gqylFZAOTmHXzK52C80DKb0Tfx_

选择: `pw3d_spin_3D/checkpoint_8.pth.tar`

### 安装

```bash
# 1. 创建目录
mkdir -p SmoothNet/data/checkpoints/pw3d_spin_3D/

# 2. 将下载的 checkpoint_8.pth.tar 放到上述目录

# 3. 验证
ls -lh SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar
# 应该显示文件大小约 50MB
```

### 验证

```bash
python -c "
import torch
ckpt = torch.load('SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar', map_location='cpu')
print('✓ Checkpoint valid')
print(f'Keys: {list(ckpt.keys())}')
"
```
```

---

## 2. Blender

### 要求
- ✅ **必须可执行**: `blender --version` 能成功运行
- ✅ **必须在 PATH 或指定路径**: 通过环境变量或常见路径找到
- ✅ **版本要求**: Blender 3.0+
- ❌ **不允许跳过**: FBX 导出是必需的

### 启动检查代码

```python
# api/services/pipeline.py

def _check_blender_or_fail(self) -> str:
    """
    检查 Blender 可用性，不可用则抛出异常
    
    Returns:
        blender_path: Blender 可执行文件路径
        
    Raises:
        RuntimeError: Blender 不可用
    """
    import shutil
    import subprocess
    
    # 1. 检查环境变量
    blender_path = os.environ.get("BLENDER_PATH")
    if blender_path:
        if Path(blender_path).exists():
            try:
                result = subprocess.run(
                    [blender_path, "--version"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                if result.returncode == 0:
                    version = result.stdout.split('\n')[0]
                    logger.info(f"✓ Blender from BLENDER_PATH: {blender_path}")
                    logger.info(f"  {version}")
                    return blender_path
            except Exception as e:
                raise RuntimeError(
                    f"❌ BLENDER_PATH is set but not executable: {blender_path}\n"
                    f"Error: {e}"
                )
        else:
            raise RuntimeError(
                f"❌ BLENDER_PATH is set but file not found: {blender_path}"
            )
    
    # 2. 检查 PATH
    blender_cmd = shutil.which("blender")
    if blender_cmd:
        try:
            result = subprocess.run(
                [blender_cmd, "--version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                logger.info(f"✓ Blender from PATH: {blender_cmd}")
                logger.info(f"  {version}")
                return blender_cmd
        except Exception:
            pass
    
    # 3. 检查常见安装路径
    common_paths = [
        "/Applications/Blender.app/Contents/MacOS/blender",  # macOS
        "/usr/bin/blender",                                   # Linux
        "/usr/local/bin/blender",                            # Linux
        "C:\\Program Files\\Blender Foundation\\Blender\\blender.exe",  # Windows
        "C:\\Program Files\\Blender Foundation\\Blender 3.6\\blender.exe",
        "C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",
    ]
    
    for path in common_paths:
        if Path(path).exists():
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                if result.returncode == 0:
                    version = result.stdout.split('\n')[0]
                    logger.info(f"✓ Blender found: {path}")
                    logger.info(f"  {version}")
                    return path
            except Exception:
                continue
    
    # 4. 未找到 Blender，抛出异常
    raise RuntimeError(
        "❌ Blender not found!\n"
        "\n"
        "Please install Blender (version 3.0+):\n"
        "\n"
        "macOS:\n"
        "  brew install --cask blender\n"
        "\n"
        "Linux (Ubuntu/Debian):\n"
        "  sudo apt update && sudo apt install blender\n"
        "\n"
        "Linux (manual):\n"
        "  wget https://www.blender.org/download/release/Blender3.6/blender-3.6.5-linux-x64.tar.xz\n"
        "  tar xf blender-3.6.5-linux-x64.tar.xz\n"
        "  sudo mv blender-3.6.5-linux-x64 /opt/blender\n"
        "  sudo ln -s /opt/blender/blender /usr/local/bin/blender\n"
        "\n"
        "Windows:\n"
        "  Download from https://www.blender.org/download/\n"
        "\n"
        "Or set BLENDER_PATH environment variable:\n"
        "  export BLENDER_PATH=/path/to/blender"
    )
```

### 用户安装文档

```markdown
## Blender 安装（必需）

### 最低版本
Blender 3.0+（推荐 3.6+）

### 安装

#### macOS
```bash
brew install --cask blender
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install blender
```

#### Linux (手动安装最新版)
```bash
# 下载
wget https://www.blender.org/download/release/Blender3.6/blender-3.6.5-linux-x64.tar.xz

# 解压
tar xf blender-3.6.5-linux-x64.tar.xz

# 安装
sudo mv blender-3.6.5-linux-x64 /opt/blender
sudo ln -s /opt/blender/blender /usr/local/bin/blender
```

#### Windows
从官网下载安装程序: https://www.blender.org/download/

### 验证

```bash
blender --version
# 输出示例:
# Blender 3.6.5
# build date: 2023-10-10
# build time: 12:00:00
```

### 环境变量（可选）

如果 Blender 不在 PATH 中，设置环境变量：

```bash
# Linux/macOS
export BLENDER_PATH=/path/to/blender

# Windows
set BLENDER_PATH=C:\Path\To\blender.exe
```
```

---

## 3. 应用启动流程

### 启动时检查

```python
# api/main.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("="*60)
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info("="*60)
    
    # 确保目录存在
    ensure_directories()
    logger.info("✓ Directories created")
    
    # 初始化 Pipeline（会检查所有依赖）
    logger.info("\nChecking dependencies...")
    try:
        pipeline = get_pipeline()
        logger.info("\n" + "="*60)
        logger.info("✓ All dependencies OK")
        logger.info("="*60 + "\n")
    except RuntimeError as e:
        logger.error("\n" + "="*60)
        logger.error("✗ Dependency check FAILED")
        logger.error("="*60)
        logger.error(f"\n{e}\n")
        logger.error("="*60)
        logger.error("Service cannot start, please fix the issues above")
        logger.error("="*60)
        raise SystemExit(1)
    
    # 启动后台工作器
    worker = get_worker()
    await worker.start()
    
    logger.info("🚀 Application started successfully\n")
    
    yield
    
    # 关闭
    logger.info("\nShutting down...")
    await worker.stop()
    logger.info("Application stopped")
```

### 成功启动输出示例

```
============================================================
Starting 4D-Humans MoCap API v1.0.0
============================================================
✓ Directories created

Checking dependencies...
✓ Blender from PATH: /usr/bin/blender
  Blender 3.6.5
✓ SmoothNet module available
✓ SmoothNet checkpoint validated: checkpoint_8.pth.tar
✓ SmoothNet ready: SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar

============================================================
✓ All dependencies OK
============================================================

🚀 Application started successfully
```

### 失败启动输出示例

```
============================================================
Starting 4D-Humans MoCap API v1.0.0
============================================================
✓ Directories created

Checking dependencies...

============================================================
✗ Dependency check FAILED
============================================================

❌ Blender not found!

Please install Blender (version 3.0+):

macOS:
  brew install --cask blender

Linux (Ubuntu/Debian):
  sudo apt update && sudo apt install blender

Windows:
  Download from https://www.blender.org/download/

Or set BLENDER_PATH environment variable:
  export BLENDER_PATH=/path/to/blender

============================================================
Service cannot start, please fix the issues above
============================================================
```

---

## 4. 配置文件

### .env 配置

```bash
# 4D-Humans MoCap API 配置

# ============================================================
# 依赖配置（必需）
# ============================================================

# Blender 路径（可选，如果在 PATH 中可不设置）
# BLENDER_PATH=/usr/bin/blender

# SmoothNet 检查点路径（必需）
SMOOTHNET_CHECKPOINT=SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar

# ============================================================
# 业务配置
# ============================================================

# 视频限制
MAX_FILE_SIZE=524288000        # 500MB
MAX_VIDEO_DURATION=30          # 30秒
MAX_VIDEO_RESOLUTION=2048      # 2K

# 队列配置
MAX_QUEUE_SIZE=10

# 超时配置（秒）
TRACKING_TIMEOUT=300
SMOOTHING_TIMEOUT=60
FBX_EXPORT_TIMEOUT=60

# 清理配置
AUTO_CLEANUP_ENABLED=true
CLEANUP_COMPLETED_HOURS=72     # 3天
CLEANUP_FAILED_HOURS=72
```

---

## 5. 快速检查脚本

创建 `scripts/check_dependencies.py`:

```python
#!/usr/bin/env python3
"""
依赖检查脚本
运行: python scripts/check_dependencies.py
"""

import sys
import subprocess
from pathlib import Path

def check_blender():
    """检查 Blender"""
    print("Checking Blender...")
    try:
        result = subprocess.run(
            ["blender", "--version"],
            capture_output=True,
            timeout=5,
            text=True
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"  ✓ {version}")
            return True
    except Exception as e:
        print(f"  ✗ Not found: {e}")
        return False

def check_smoothnet():
    """检查 SmoothNet"""
    print("Checking SmoothNet...")
    
    checkpoint = Path("SmoothNet/data/checkpoints/pw3d_spin_3D/checkpoint_8.pth.tar")
    if not checkpoint.exists():
        print(f"  ✗ Checkpoint not found: {checkpoint}")
        return False
    
    try:
        import torch
        ckpt = torch.load(checkpoint, map_location='cpu')
        print(f"  ✓ Checkpoint OK: {checkpoint.name}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to load: {e}")
        return False

def main():
    print("="*60)
    print("4D-Humans MoCap API - Dependency Check")
    print("="*60)
    print()
    
    checks = {
        "Blender": check_blender(),
        "SmoothNet": check_smoothnet()
    }
    
    print()
    print("="*60)
    if all(checks.values()):
        print("✓ All dependencies OK")
        print("="*60)
        return 0
    else:
        print("✗ Some dependencies missing")
        print("="*60)
        print("\nPlease fix the issues above before starting the service.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

运行检查:
```bash
python scripts/check_dependencies.py
```

---

## 总结

### 强制要求
1. ✅ **SmoothNet 检查点必须存在且可加载**
2. ✅ **Blender 必须可执行**
3. ❌ **不提供任何降级策略**
4. ❌ **依赖不满足时服务无法启动**

### 用户体验
- 启动时立即检查所有依赖
- 清晰的错误提示和安装指引
- 提供独立的检查脚本
- 详细的安装文档

